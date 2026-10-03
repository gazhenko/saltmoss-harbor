using System;
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// Professor Inkwell's Tidewrack Museum: donate treasures (and the first of every fish and crab) from Pip's pocket
    /// and the hold/cold store. Each donation gets its own little lecture and appears in the cabinets for good.
    /// </summary>
    public class Museum : MonoBehaviour
    {
        public static Museum I { get; private set; }
        public Transform[] treasureSlots = new Transform[0];
        public Transform[] fishSlots = new Transform[0];
        readonly Dictionary<string, GameObject> shown = new Dictionary<string, GameObject>();

        Canvas canvas;
        RectTransform grid;
        TextMeshProUGUI header;
        readonly List<GameObject> cells = new List<GameObject>();
        Action done;
        bool open;
        float openedAt;

        void Awake() { I = this; }

        void Start()
        {
            Refresh();
            GameFlow.On("donate", (args, d) => Open(d));
        }

        /// <summary>Everything Pip holds that the museum doesn't have yet.</summary>
        public static List<string> Donatable()
        {
            var D = GameState.D;
            var ids = new List<string>();
            foreach (var list in new[] { D.pocket, D.stock, D.hold })
                foreach (var s in list)
                {
                    var def = Catalog.Get(s.id);
                    if (def != null && def.Donatable && !D.donated.Contains(s.id) && !ids.Contains(s.id)) ids.Add(s.id);
                }
            return ids;
        }

        public void Refresh()
        {
            int ti = 0, fi = 0;
            foreach (var id in GameState.D.donated)
            {
                var def = Catalog.Get(id);
                if (def == null) continue;
                bool treasure = def.kind == Kind.Treasure;
                var slots = treasure ? treasureSlots : fishSlots;
                int idx = treasure ? ti++ : fi++;
                if (idx >= slots.Length || slots[idx] == null || shown.ContainsKey(id)) continue;
                var go = ModelBank.I.Spawn(def.model, slots[idx].position, slots[idx].rotation * Quaternion.Euler(0, 160f, 0), slots[idx]);
                float size = go.GetComponent<ClayModel>()?.VisualBounds().size.magnitude ?? 0.5f;
                float max = treasure ? 0.7f : 0.9f;
                if (size > max) go.transform.localScale = Vector3.one * (max / size);
                shown[id] = go;
            }
        }

        void Build()
        {
            canvas = ClayUI.Canvas("MuseumCanvas", 45, transform);
            var panel = ClayUI.Panel("Panel", canvas.transform, "panel_cream", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1300f, 760f));
            header = ClayUI.Text("Title", panel.transform, "", 46f, new Color32(0x8a, 0x3b, 0x5c, 255), TextAlignmentOptions.Top, true);
            header.margin = new Vector4(30, 30, 30, 0);
            grid = ClayUI.Rect("Grid", panel.transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0f, -40f), new Vector2(1160f, 560f));
            var gl = grid.gameObject.AddComponent<GridLayoutGroup>();
            gl.cellSize = new Vector2(176f, 200f);
            gl.spacing = new Vector2(18f, 18f);
            gl.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            gl.constraintCount = 6;
            gl.childAlignment = TextAnchor.UpperCenter;
            ClayUI.Button("Done", panel.transform, "That's all for now", new Vector2(0.5f, 0f), new Vector2(0f, 40f), new Vector2(460f, 86f), Close, 30f);
            canvas.gameObject.SetActive(false);
        }

        public void Open(Action onDone)
        {
            if (canvas == null) Build();
            done = onDone;
            open = true;
            openedAt = Time.unscaledTime;
            if (GameFlow.I != null) GameFlow.I.InMenu = true;
            canvas.gameObject.SetActive(true);
            DialogueUI.Suspended = true;
            Fill();
        }

        void Fill()
        {
            foreach (var c in cells) Destroy(c);
            cells.Clear();
            var ids = Donatable();
            header.text = ids.Count > 0 ? "What would you like to donate?" : "Nothing new for the collection right now.";
            Button first = null;
            foreach (var id in ids)
            {
                var def = Catalog.Get(id);
                var cell = ClayUI.Panel("Cell", grid, "slot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(176f, 200f));
                cell.raycastTarget = true;
                var b = cell.gameObject.AddComponent<Button>();
                var cb = b.colors; cb.selectedColor = new Color(1f, 0.85f, 0.5f); cb.highlightedColor = cb.selectedColor; b.colors = cb;
                string pid = id;
                b.onClick.AddListener(() => Donate(pid));
                cell.gameObject.AddComponent<Squish>();
                var ic = ClayUI.Panel("Icon", cell.transform, null, new Vector2(0.5f, 0.6f), Vector2.zero, new Vector2(130f, 130f));
                ic.sprite = ItemStage.Ensure().Icon(id);
                ic.color = Color.white;
                ic.preserveAspect = true;
                var t = ClayUI.Text("Label", cell.transform, def.name, 22f, ClayUI.Ink, TextAlignmentOptions.Bottom);
                t.margin = new Vector4(8, 0, 8, 12);
                cells.Add(cell.gameObject);
                if (first == null) first = b;
            }
            if (first != null) ClayUI.Select(first);
            else ClayUI.Select(canvas.GetComponentInChildren<Button>());
        }

        void Donate(string id)
        {
            if (Time.unscaledTime - openedAt < 0.25f) return;
            var D = GameState.D;
            var def = Catalog.Get(id);
            if (def == null || D.donated.Contains(id)) return;
            // take one: treasure from the pocket, fish/crabs from the stock or hold
            foreach (var list in new[] { D.pocket, D.stock, D.hold })
                if (GameState.Count(list, id) > 0) { GameState.Remove(list, id, 1); break; }
            D.donated.Add(id);
            GameState.SetFlag("donated_first");
            GameState.Notify();
            AudioDirector.UI("stamp", 0.9f);
            AudioDirector.I?.Jingle("jingle_donation");
            Refresh();
            canvas.gameObject.SetActive(false);
            DialogueUI.Suspended = false;
            // the professor's little lecture
            DialogueRunner.Vars["item"] = def.name;
            DialogueRunner.Vars["lore"] = string.IsNullOrEmpty(def.lore) ? "A fine specimen." : def.lore;
            StartCoroutine(Lecture());
        }

        IEnumerator Lecture()
        {
            // the runner is busy with the hub conversation; show the lore as a direct toast-style aside via the UI
            var ui = DialogueUI.Ensure();
            ui.SetSpeaker("inkwell");
            var pFace = PortraitStage.I?.Face("inkwell");
            if (pFace != null) pFace.expression = Expr.Happy;
            string text = $"Ah, the {DialogueRunner.Vars["item"]}! {DialogueRunner.Vars["lore"]}";
            ui.SetText(text);
            int total = ui.Total;
            float acc = 0f;
            int vis = 0;
            var anim = PortraitStage.I?.Anim("inkwell");
            if (anim != null) anim.talking = true;
            while (vis < total)
            {
                acc += Time.unscaledDeltaTime * 34f * Settings.TextSpeed;
                while (acc >= 1f && vis < total)
                {
                    char c = ui.CharAt(vis++);
                    acc -= 1f;
                    if (char.IsLetter(c) && VoiceBlips.I != null && VoiceBlips.I.Speak("inkwell", c)) pFace?.Syllable(c);
                }
                ui.Visible = vis;
                if (GameInput.Confirm.WasPressedThisFrame()) { vis = total; ui.Visible = total; }
                yield return null;
            }
            if (anim != null) anim.talking = false;
            ui.ShowArrow(true);
            yield return null;
            while (!GameInput.Confirm.WasPressedThisFrame()) yield return null;
            ui.ShowArrow(false);
            Restoration.Check();
            if (Donatable().Count > 0) { canvas.gameObject.SetActive(true); DialogueUI.Suspended = true; openedAt = Time.unscaledTime; Fill(); }
            else Close();
        }

        void Close()
        {
            if (!open) return;
            open = false;
            canvas.gameObject.SetActive(false);
            DialogueUI.Suspended = false;
            if (GameFlow.I != null) GameFlow.I.InMenu = false;
            var d = done;
            done = null;
            d?.Invoke();
        }

        void Update()
        {
            if (open && canvas.gameObject.activeSelf && GameInput.Back.WasPressedThisFrame()) Close();
        }
    }
}
