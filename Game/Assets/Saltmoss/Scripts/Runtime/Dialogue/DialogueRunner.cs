using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Plays dialogue nodes: typewriter text with voice blips and talking puppets (in the world and in the portrait),
    /// expressions and gestures from the script, choices, flags/money/items, and hooks into the game (shops, museum,
    /// sleep…) through <see cref="GameFlow.Event"/>. Frames a two-shot of Pip and whoever they're talking to.
    /// </summary>
    public class DialogueRunner : MonoBehaviour
    {
        public static DialogueRunner I { get; private set; }
        public static bool Active { get; private set; }
        public static event Action<string> NodeStarted;

        public class WorldActor
        {
            public Transform root;
            public FaceRig face;
            public CritterAnimator anim;
        }

        static readonly Dictionary<string, WorldActor> actors = new Dictionary<string, WorldActor>();
        public static readonly Dictionary<string, string> Vars = new Dictionary<string, string>();
        readonly List<DialogueScript.Mark> marks = new List<DialogueScript.Mark>();
        string partner;
        Action onDone;
        float inputGuard;

        public static void Register(string id, Transform root, FaceRig face, CritterAnimator anim)
        {
            actors[id] = new WorldActor { root = root, face = face, anim = anim };
        }

        public static WorldActor Actor(string id) => id != null && actors.TryGetValue(id, out var a) ? a : null;

        static DialogueRunner Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("DialogueRunner");
            DontDestroyOnLoad(go);
            I = go.AddComponent<DialogueRunner>();
            return I;
        }

        /// <summary>Stop any conversation immediately (trailer cuts, scene changes).</summary>
        public static void Abort()
        {
            if (I == null || !Active) return;
            I.StopAllCoroutines();
            DialogueUI.I?.Show(false);
            foreach (var a in actors.Values) if (a.anim != null) a.anim.talking = false;
            CameraRig.I?.ClearOverride();
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            Active = false;
            I.onDone = null;
        }

        /// <summary>Start a conversation at a node. partnerId = the NPC Pip is talking to (for framing/facing).</summary>
        public static void Play(string node, string partnerId = null, Action done = null)
        {
            if (Active) return;
            if (!DialogueScript.Has(node)) { Debug.LogWarning("[Dialogue] missing node " + node); done?.Invoke(); return; }
            var r = Ensure();
            r.partner = partnerId;
            r.onDone = done;
            r.StartCoroutine(r.Run(node));
        }

        IEnumerator Run(string node)
        {
            Active = true;
            PlayerController.LockCount++;
            var ui = DialogueUI.Ensure();
            Vars["name"] = "Pip";
            Vars["money"] = GameState.D.money.ToString();
            Vars["day"] = GameState.D.day.ToString();
            FacePartner();
            FrameTwoShot();
            ui.Show(true);
            string cur = node;
            while (!string.IsNullOrEmpty(cur) && cur != "end")
            {
                NodeStarted?.Invoke(cur);
                var steps = DialogueScript.Node(cur);
                if (steps == null) { Debug.LogWarning("[Dialogue] missing node " + cur); break; }
                string next = null;
                for (int i = 0; i < steps.Count && next == null; i++)
                {
                    var s = steps[i];
                    switch (s.kind)
                    {
                        case DialogueScript.StepKind.Line:
                            yield return Line(ui, s);
                            break;
                        case DialogueScript.StepKind.Goto:
                            next = s.target;
                            break;
                        case DialogueScript.StepKind.Choice:
                        {
                            var shown = new List<DialogueScript.Choice>();
                            foreach (var c in s.choices) if (Cond(c.cond)) shown.Add(c);
                            if (shown.Count == 0) break;
                            int picked = -1;
                            ui.ShowArrow(false);
                            var labels = shown.ConvertAll(c => Interp(c.label));
                            ui.ShowChoices(labels, k => picked = k);
                            AudioDirector.UI("ui_open", 0.6f);
                            while (picked < 0) yield return null;
                            ui.HideChoices();
                            next = shown[picked].target;
                            break;
                        }
                        case DialogueScript.StepKind.Command:
                        {
                            string jump = null;
                            yield return Command(s, t => jump = t);
                            if (jump != null) next = jump;
                            break;
                        }
                    }
                }
                cur = next ?? "end";
            }
            ui.Show(false);
            foreach (var a in actors.Values) if (a.anim != null) a.anim.talking = false;
            CameraRig.I?.ClearOverride();
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            Active = false;
            var done = onDone;
            onDone = null;
            done?.Invoke();
        }

        string Interp(string s)
        {
            foreach (var kv in Vars) s = s.Replace("{" + kv.Key + "}", kv.Value);
            return s;
        }

        IEnumerator Line(DialogueUI ui, DialogueScript.Step s)
        {
            string speaker = s.speaker;
            var member = Cast.Get(speaker);
            var world = Actor(speaker);
            ui.SetSpeaker(speaker);
            var pFace = PortraitStage.I != null ? PortraitStage.I.Face(speaker) : null;
            var pAnim = PortraitStage.I != null ? PortraitStage.I.Anim(speaker) : null;
            SetExpr(speaker, FaceRig.Parse(s.expr), world, pFace);
            if (world?.anim != null) world.anim.talking = true;
            if (pAnim != null) pAnim.talking = true;
            if (world?.face != null && Actor("pip") != null && speaker != "pip") world.face.lookTarget = Actor("pip").root;

            Vars["money"] = GameState.D.money.ToString();
            string rich = DialogueScript.Compile(s.text, Vars, marks);
            ui.SetText(rich);
            ui.ShowArrow(false);
            int total = ui.Total;
            var contour = Contour(ui, total, out var emph);
            float cps = 34f * Settings.TextSpeed;
            float spd = 1f, acc = 0f;
            int vis = 0, mi = 0;
            inputGuard = 0.18f;
            while (vis < total)
            {
                inputGuard -= Time.unscaledDeltaTime;
                while (mi < marks.Count && marks[mi].index <= vis)
                {
                    var m = marks[mi++];
                    if (m.kind == DialogueScript.MarkKind.Expr) SetExpr(speaker, FaceRig.Parse(m.value), world, pFace);
                    else if (m.kind == DialogueScript.MarkKind.Speed) spd = m.f;
                    else if (m.kind == DialogueScript.MarkKind.Pause) acc -= m.f * cps;
                }
                if (inputGuard <= 0f && GameInput.Confirm.WasPressedThisFrame())
                {
                    vis = total;
                    while (mi < marks.Count) { var m = marks[mi++]; if (m.kind == DialogueScript.MarkKind.Expr) SetExpr(speaker, FaceRig.Parse(m.value), world, pFace); }
                    break;
                }
                float fast = GameInput.Run.IsPressed() ? 3f : 1f;
                acc += Time.unscaledDeltaTime * cps * spd * fast;
                while (acc >= 1f && vis < total)
                {
                    char c = ui.CharAt(vis);
                    vis++;
                    acc -= 1f;
                    if (char.IsLetter(c))
                    {
                        if (speaker != "narrator" && VoiceBlips.I != null && VoiceBlips.I.Speak(member.voice, c, contour[vis - 1], emph[vis - 1]))
                        {
                            world?.face?.Syllable(c, 0.6f + emph[vis - 1]);
                            pFace?.Syllable(c, 0.6f + emph[vis - 1]);
                        }
                    }
                    else if (c == ',' || c == ';' || c == ':') acc -= 0.16f * cps;
                    else if ((c == '.' || c == '!' || c == '?' || c == '…') && (vis >= total || ui.CharAt(vis) == ' '))
                        acc -= (c == '…' ? 0.45f : 0.3f) * cps;
                    else if (c == '—') acc -= 0.2f * cps;
                }
                ui.Visible = vis;
                yield return null;
            }
            ui.Visible = total;
            if (world?.anim != null) world.anim.talking = false;
            if (pAnim != null) pAnim.talking = false;
            ui.ShowArrow(true);
            inputGuard = 0.12f;
            while (true)
            {
                inputGuard -= Time.unscaledDeltaTime;
                if (inputGuard <= 0f && GameInput.Confirm.WasPressedThisFrame()) break;
                yield return null;
            }
            AudioDirector.UI("dialogue_next", 0.5f);
        }

        /// <summary>Per-character intonation: statements arch and fall, questions rise at the end, exclamations punch.</summary>
        static float[] Contour(DialogueUI ui, int total, out float[] emph)
        {
            var c = new float[Mathf.Max(1, total)];
            emph = new float[Mathf.Max(1, total)];
            int start = 0;
            for (int i = 0; i <= total; i++)
            {
                char ch = i < total ? ui.CharAt(i) : '.';
                bool end = i == total || ch == '.' || ch == '!' || ch == '?' || ch == '…';
                if (!end) continue;
                int len = Mathf.Max(1, i - start);
                for (int j = start; j < i && j < total; j++)
                {
                    float k = (j - start) / (float)len;
                    float v = 0.3f * Mathf.Sin(k * Mathf.PI) - 0.25f * k;
                    if (ch == '?') v += 1.0f * k * k;
                    if (ch == '!') { v += 0.25f; emph[j] = 0.45f; }
                    if (char.IsUpper(ui.CharAt(j)) && j + 1 < total && char.IsUpper(ui.CharAt(j + 1))) emph[j] = 0.8f;
                    c[j] = v;
                }
                start = i + 1;
            }
            return c;
        }

        void SetExpr(string who, Expr e, WorldActor world, FaceRig portrait)
        {
            if (world?.face != null) world.face.expression = e;
            if (portrait != null) portrait.expression = e;
        }

        void FacePartner()
        {
            var pip = Actor("pip");
            var other = Actor(partner);
            if (pip == null || other == null) return;
            var d = other.root.position - pip.root.position;
            d.y = 0f;
            if (d.sqrMagnitude < 0.01f) return;
            pip.root.rotation = Quaternion.LookRotation(d);
            other.root.rotation = Quaternion.LookRotation(-d);
            if (pip.face) pip.face.lookTarget = other.root;
            if (other.face) other.face.lookTarget = pip.root;
        }

        /// <summary>Over Pip's shoulder onto whoever they're talking to — Pip always stands in open space.</summary>
        void FrameTwoShot()
        {
            var pip = Actor("pip");
            var other = Actor(partner);
            var rig = CameraRig.I;
            if (pip == null || other == null || rig == null) return;
            Vector3 a = pip.root.position, b = other.root.position;
            float h = Mathf.Max(0.9f, ModelHeight(other));
            var line = b - a;
            line.y = 0f;
            var fwd = line.sqrMagnitude > 0.01f ? line.normalized : pip.root.forward;
            var side = Vector3.Cross(Vector3.up, fwd);
            var camNow = Camera.main != null ? Camera.main.transform.position : a - fwd;
            if (Vector3.Dot(camNow - a, side) < 0f) side = -side;
            var look = b + Vector3.up * (h * 0.72f) - fwd * 0.2f;
            var pos = a - fwd * (1.6f + h * 0.6f) + side * (0.9f + h * 0.25f) + Vector3.up * (0.9f + h * 0.45f);
            // keep the camera in the open on Pip's side (the partner may well be behind a counter window)
            var eye = a + Vector3.up * 1.0f;
            var toCam = pos - eye;
            if (Physics.SphereCast(eye, 0.25f, toCam.normalized, out var hit, toCam.magnitude, 1 << 10, QueryTriggerInteraction.Ignore))
                pos = eye + toCam.normalized * Mathf.Max(0.6f, hit.distance - 0.2f);
            rig.SetOverride(pos, Quaternion.LookRotation(look - pos), 34f);
        }

        static float ModelHeight(WorldActor a)
        {
            var m = a.root.GetComponentInChildren<ClayModel>();
            return m != null ? m.VisualBounds().size.y : 1f;
        }

        IEnumerator Command(DialogueScript.Step s, Action<string> jump)
        {
            var a = s.args;
            string A(int i) => i < a.Length ? a[i] : null;
            switch (s.cmd)
            {
                case "flag": GameState.SetFlag(A(0)); break;
                case "unflag": GameState.D.flags.Remove(A(0)); break;
                case "money":
                    if (int.TryParse(A(0), out var m))
                    {
                        if (m >= 0) GameState.Earn(m, false); else GameState.Spend(-m);
                        AudioDirector.UI("coin", 0.7f);
                    }
                    break;
                case "give":
                {
                    var def = Catalog.Get(A(0));
                    int n = A(1) != null ? int.Parse(A(1)) : 1;
                    if (def != null) GameState.Add(def.kind == Kind.Fish || def.kind == Kind.Crab ? GameState.D.stock : GameState.D.pocket, def.id, n);
                    AudioDirector.UI("item_get", 0.7f);
                    break;
                }
                case "take":
                {
                    string id = A(0);
                    int n = A(1) != null ? int.Parse(A(1)) : 1;
                    foreach (var list in new[] { GameState.D.pocket, GameState.D.stock, GameState.D.hold })
                    {
                        int have = GameState.Count(list, id);
                        int take = Mathf.Min(have, n);
                        if (take > 0) { GameState.Remove(list, id, take); n -= take; }
                    }
                    break;
                }
                case "gesture":
                {
                    var g = (Gesture)Enum.Parse(typeof(Gesture), A(1), true);
                    Actor(A(0))?.anim?.Play(g, A(2) != null ? float.Parse(A(2), CultureInfo.InvariantCulture) : 1.2f);
                    PortraitStage.I?.Anim(A(0)).Play(g, 1.2f);
                    break;
                }
                case "expr":
                {
                    var e = FaceRig.Parse(A(1));
                    var w = Actor(A(0));
                    if (w?.face != null) w.face.expression = e;
                    if (PortraitStage.I != null) PortraitStage.I.Face(A(0)).expression = e;
                    break;
                }
                case "mumble":
                {
                    string text = a.Length > 1 ? string.Join(" ", a, 1, a.Length - 1) : null;
                    float d = VoiceBlips.I != null ? VoiceBlips.I.Mumble(Cast.Get(A(0)).voice, text) : 0.5f;
                    Actor(A(0))?.face?.Bounce();
                    yield return new WaitForSecondsRealtime(Mathf.Min(d, 1.4f));
                    break;
                }
                case "jingle": AudioDirector.I?.Jingle(A(0)); break;
                case "sfx": AudioDirector.UI(A(0)); break;
                case "wait": yield return new WaitForSecondsRealtime(float.Parse(A(0), CultureInfo.InvariantCulture)); break;
                case "set": Vars[A(0)] = string.Join(" ", a, 1, a.Length - 1); break;
                case "if": if (Cond(string.Join(" ", a))) jump(s.target); break;
                case "end": jump("end"); break;
                case "event":
                {
                    bool done = false;
                    GameFlow.Event(A(0), a, () => done = true);
                    while (!done) yield return null;
                    break;
                }
                default: Debug.LogWarning($"[Dialogue] unknown command !{s.cmd} (line {s.lineNo})"); break;
            }
        }

        /// <summary>flag:x, !flag:x, money>=n, has:item[:n], day>=n, restoration>=n, donated>=n, upgrade:x, found:x, night, storm.</summary>
        public static bool Cond(string cond)
        {
            if (string.IsNullOrWhiteSpace(cond)) return true;
            cond = cond.Trim();
            if (cond.StartsWith("if ")) cond = cond.Substring(3).Trim();
            if (cond.Contains(" and "))
            {
                foreach (var part in cond.Split(new[] { " and " }, StringSplitOptions.None)) if (!Cond(part)) return false;
                return true;
            }
            bool neg = false;
            if (cond.StartsWith("unless ")) { neg = true; cond = cond.Substring(7).Trim(); }
            if (cond.StartsWith("!")) { neg = !neg; cond = cond.Substring(1); }
            bool r = Eval(cond);
            return neg ? !r : r;
        }

        static bool Eval(string c)
        {
            var D = GameState.D;
            if (c.StartsWith("flag:")) return GameState.Flag(c.Substring(5));
            if (c.StartsWith("upgrade:")) return GameState.Has(c.Substring(8));
            if (c.StartsWith("found:")) return D.discovered.Contains(c.Substring(6));
            if (c.StartsWith("donated:")) return D.donated.Contains(c.Substring(8));
            if (c.StartsWith("has:"))
            {
                var p = c.Substring(4).Split(':');
                int need = p.Length > 1 ? int.Parse(p[1]) : 1;
                return GameState.Count(D.pocket, p[0]) + GameState.Count(D.stock, p[0]) + GameState.Count(D.hold, p[0]) >= need;
            }
            if (c == "night") return DayCycle.I != null && DayCycle.I.IsNight;
            if (c == "storm") return D.weather >= (int)Weather.Squalls;
            if (Compare(c, "money", D.money, out bool r)) return r;
            if (Compare(c, "day", D.day, out r)) return r;
            if (Compare(c, "restoration", D.restoration, out r)) return r;
            if (Compare(c, "donated", D.donated.Count, out r)) return r;
            if (Compare(c, "sales", D.totalSales, out r)) return r;
            if (Compare(c, "hour", (int)D.hour, out r)) return r;
            if (Compare(c, "stock", GameState.Count(D.stock), out r)) return r;
            if (Compare(c, "hold", GameState.Count(D.hold), out r)) return r;
            if (Compare(c, "orders", D.letters.Count, out r)) return r;
            if (c.StartsWith("var:"))
            {
                // var:name==value (string compare on dialogue variables)
                var body = c.Substring(4);
                int eq = body.IndexOf("==");
                if (eq > 0) return Vars.TryGetValue(body.Substring(0, eq), out var vv) && vv == body.Substring(eq + 2);
                return Vars.ContainsKey(body) && !string.IsNullOrEmpty(Vars[body]);
            }
            Debug.LogWarning("[Dialogue] unknown condition " + c);
            return false;
        }

        static bool Compare(string c, string key, int value, out bool result)
        {
            result = false;
            if (!c.StartsWith(key)) return false;
            string rest = c.Substring(key.Length);
            string[] ops = { ">=", "<=", "==", ">", "<" };
            foreach (var op in ops)
            {
                if (!rest.StartsWith(op)) continue;
                int n = int.Parse(rest.Substring(op.Length));
                result = op == ">=" ? value >= n : op == "<=" ? value <= n : op == "==" ? value == n : op == ">" ? value > n : value < n;
                return true;
            }
            return false;
        }
    }
}
