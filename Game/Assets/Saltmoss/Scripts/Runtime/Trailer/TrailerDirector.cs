using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Films the trailer inside the game: each shot stages a real scene (time of day, weather, who stands where, what
    /// happens), moves the camera along a scripted path, and records frames at a fixed 24 fps — so the 12 fps world
    /// lands exactly on twos, like stop-motion film — plus the game's own audio (voice blips, sea, winch) through the
    /// AudioRenderer. Run: player -trailer -capture DIR [-only a,b,c]. Edited by Tools/trailer/edit.py.
    /// </summary>
    [DefaultExecutionOrder(9200)]
    public class TrailerDirector : MonoBehaviour
    {
        public static bool Requested => CommandLine.Has("-trailer");
        const int Fps = 24;

        class Shot
        {
            public string name;
            public float dur;
            public Action setup;
            public Func<float, (Vector3 pos, Vector3 look, float fov)> cam;
            public List<(float t, Action a)> events = new List<(float, Action)>();
            public Action<float> tick;
        }

        readonly List<Shot> shots = new List<Shot>();
        Shot current;
        float shotT;
        Camera cam;
        Transform focus;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (!Requested) return;
            var go = new GameObject("TrailerDirector");
            DontDestroyOnLoad(go);
            go.AddComponent<TrailerDirector>();
        }

        // ---------------------------------------------------------------- helpers
        static Transform Actor(string id) => DialogueRunner.Actor(id)?.root;
        static Vector3 A(Transform t, float x, float y, float z) => t == null ? new Vector3(x, y, z) : t.TransformPoint(new Vector3(x, y, z));
        static WorldRefs R => WorldRefs.I;
        static PlayerController Pip => PlayerController.I;
        static BoatController Boat => BoatController.I;

        static void Hour(float h, int weather = 0)
        {
            GameState.D.hour = h;
            GameState.D.weather = weather;
            if (DayCycle.I != null) { DayCycle.I.hour = h; DayCycle.I.frozen = true; }
        }

        static (Vector3, Vector3, float) Dolly(Vector3 a, Vector3 b, Vector3 la, Vector3 lb, float t, float fov = 32f)
        {
            float e = Mathf.SmoothStep(0f, 1f, t);
            return (Vector3.Lerp(a, b, e), Vector3.Lerp(la, lb, e), fov);
        }

        static void BoatAt(Vector3 p, float yaw, float speed, float turn = 0f)
        {
            var b = Boat;
            if (b == null) return;
            if (!b.Aboard) b.Board();
            b.autopilot = true;
            b.autoSpeed = speed;
            b.autoTurn = turn;
            b.transform.SetPositionAndRotation(new Vector3(p.x, 0f, p.z), Quaternion.Euler(0f, yaw, 0f));
            b.puppet?.Snap();
        }

        static void Ashore(Vector3 pos, float yaw)
        {
            var b = Boat;
            if (b != null && b.Aboard) { b.autopilot = false; b.ForceDock(); Pip.Disembark(pos, yaw); }
            else Pip.Teleport(pos, yaw);
        }

        static void Clear()
        {
            DialogueRunner.Abort();
            CatchReveal.I?.Abort();
            MiniGameUI.I?.Hide();
            if (ShopCounter.I != null && ShopCounter.I.Open) ShopCounter.I.Close();
            GameState.D.pots.Clear();
            CrabPots.I?.Resync();
            if (Boat != null) { Boat.Ice = 0f; Boat.Sputter = 0f; }
            Pip.anim.activity = Activity.None;
            if (SeaState.I != null) SeaState.I.storm = 0f;
        }

        // ---------------------------------------------------------------- the shot list
        void Plan()
        {
            Vector3 mouth = Boat != null ? new Vector3(Boat.harbourMouth.x, 0, Boat.harbourMouth.y) : new Vector3(0, 0, 75);
            var shop = R.shopStand;
            var walter = Actor("walter");
            var nell = Actor("nell");
            var inkwell = Actor("inkwell");
            var shelby = Actor("shelby");

            Add("dawn_harbor", 6.5f, () => { Hour(6.7f); Ashore(R.playerSpawn.position, R.playerSpawn.eulerAngles.y); },
                t => Dolly(mouth + new Vector3(-40, 22, -10), mouth + new Vector3(-10, 14, -30), new Vector3(0, 2, 0), new Vector3(-2, 2, -6), t, 34f));

            Add("pip_pier", 4.5f, () =>
            {
                Hour(8.6f);
                Pip.Teleport(new Vector3(0f, 1.8f, 3f), 0f);
            }, t => Dolly(new Vector3(1.3f, 2.8f, 15f), new Vector3(1.0f, 2.6f, 16.5f), Pip.transform.position + Vector3.up * 0.6f, Pip.transform.position + Vector3.up * 0.6f, t, 30f)).tick = t =>
            {
                Pip.anim.speed = 1.6f;
                Pip.transform.position += Vector3.forward * 1.6f * Time.deltaTime;
            };

            Add("walter_talk", 6f, () =>
            {
                Hour(9.2f);
                if (walter != null) Pip.Teleport(A(walter, 0f, 0f, 2.1f), walter.eulerAngles.y + 180f);
                DialogueRunner.Play("trailer_walter", "walter");
            }, t =>
            {
                var w = walter != null ? walter.position : Vector3.zero;
                var a = Pip.transform.position;
                var fwd = (w - a); fwd.y = 0f; fwd.Normalize();
                var side = Vector3.Cross(Vector3.up, fwd);
                var look = w + Vector3.up * 1.15f;
                var p0 = a - fwd * 2.6f + side * 1.2f + Vector3.up * 1.7f;
                var p1 = a - fwd * 2.0f + side * 0.9f + Vector3.up * 1.6f;
                return Dolly(p0, p1, look, look, t, 32f);
            });

            Add("nell_shop", 4f, () =>
            {
                Hour(10f);
                GameState.D.stock.Clear();
                foreach (var id in new[] { "herring", "mackerel", "cod", "salmon", "dungeness", "flounder", "halibut", "snow_crab" }) GameState.Add(GameState.D.stock, id, 3);
                ShopCounter.I?.RefreshDisplay();
                Pip.Teleport(A(shop, 0f, 0f, 4.2f), shop.eulerAngles.y + 180f);
                nell?.GetComponentInChildren<CritterAnimator>()?.Play(Gesture.Wave, 2f);
            }, t => Dolly(A(shop, 2.5f, 1.6f, 6.5f), A(shop, 1.6f, 1.4f, 4.6f), A(shop, -0.5f, 1.2f, 0f), A(shop, -0.5f, 1.1f, 0f), t, 32f));

            Add("boat_out", 6.5f, () => { Hour(11f); Clear(); BoatAt(mouth + new Vector3(4, 0, -38), 2f, 7.5f); },
                t =>
                {
                    var b = Boat.transform;
                    return Dolly(A(b, 9f, 3.2f, -6f), A(b, 7f, 2.6f, 4f), b.position + Vector3.up * 2f, b.position + Vector3.up * 2f + b.forward * 3f, t, 34f);
                });

            Add("storm_hit", 4f, () =>
            {
                Hour(15f, (int)Weather.Storm);
                BoatAt(mouth + new Vector3(-60, 0, 520), 20f, 5f);
                if (SeaState.I != null) SeaState.I.storm = 1f;
                if (DayCycle.I != null) { DayCycle.I.storm = 0.9f; DayCycle.I.overcast = 0.95f; }
            }, t =>
            {
                var b = Boat.transform;
                return Dolly(A(b, -7f, 1.4f, 10f), A(b, -8f, 1.8f, 7f), b.position + Vector3.up * 1.6f, b.position + Vector3.up * 2.2f, t, 36f);
            }).events.Add((1.0f, () =>
            {
                var b = Boat;
                AudioDirector.Play("wave_crash_big", b.transform.position, 1f, 0f);
                for (int i = 0; i < 26; i++) CottonPuff.Emit(b.transform.position + b.transform.forward * 4f + UnityEngine.Random.insideUnitSphere * 2.5f, Color.white, 0.9f, new Vector3(UnityEngine.Random.Range(-2f, 2f), UnityEngine.Random.Range(3f, 8f), UnityEngine.Random.Range(-3f, 1f)), 1.5f);
                if (b.puppet != null) b.puppet.offsetRot *= Quaternion.Euler(-16f, 0, 8f);
            }));

            Add("haul_pot", 4.5f, () =>
            {
                Hour(13f, (int)Weather.Breezy);
                if (DayCycle.I != null) { DayCycle.I.storm = 0f; DayCycle.I.overcast = 0.2f; }
                if (SeaState.I != null) SeaState.I.storm = 0.1f;
                BoatAt(mouth + new Vector3(30, 0, 220), 100f, 0f);
                Pip.MoveAboard(Boat.winch != null ? Boat.winch : Boat.helm, Activity.Haul);
                MiniGameUI.Ensure().Show("HAUL!", "Hold to winch — keep the needle in the green", "too tight", "slack");
            }, t =>
            {
                var b = Boat.transform;
                return Dolly(A(b, -6.5f, 3.4f, 2f), A(b, -5.5f, 2.8f, 0.5f), b.position + Vector3.up * 1.4f, b.position + Vector3.up * 1.2f, t, 34f);
            }).tick = t =>
            {
                Pip.anim.activityPhase = Mathf.Repeat(t * 3f, 1f);
                float c = 0.5f + Mathf.Sin(t * 4f) * 0.15f;
                MiniGameUI.I.Set(c, 0.24f, c + Mathf.Sin(t * 9f) * 0.06f, Mathf.Clamp01(t / 0.75f), true);
                if (t > 0.78f && MiniGameUI.I != null) { MiniGameUI.I.Hide(); }
            };
            shots[shots.Count - 1].events.Add((3.5f, () =>
            {
                AudioDirector.Play("crab_clatter", Boat.transform.position, 1f);
                DeckCatch.Spill(Boat, new Dictionary<string, int> { ["dungeness"] = 3, ["snow_crab"] = 2, ["sea_urchin"] = 1 });
            }));

            Add("cast_catch", 5f, () =>
            {
                Hour(16.4f);
                BoatAt(mouth + new Vector3(-50, 0, 140), 60f, 0f);
                Pip.MoveAboard(Boat.rail != null ? Boat.rail : Boat.helm, Activity.Cast);
            }, t =>
            {
                var b = Boat.transform;
                return Dolly(A(b, 6f, 2.6f, 7f), A(b, 4.5f, 2.2f, 5.5f), Pip.transform.position + Vector3.up * 0.8f, Pip.transform.position + Vector3.up * 0.8f, t, 32f);
            }).tick = t => Pip.anim.activityPhase = Mathf.Clamp01(t * 3f);
            shots[shots.Count - 1].events.Add((2.2f, () => { CatchReveal.Ensure().Enqueue(Catalog.Get("salmon"), true); }));

            Add("treasure", 4.5f, () =>
            {
                Hour(14.5f);
                BoatAt(mouth + new Vector3(-130, 0, 460), 200f, 0f);
                Pip.MoveAboard(Boat.winch != null ? Boat.winch : Boat.helm, Activity.Crank);
            }, t =>
            {
                var b = Boat.transform;
                return Dolly(A(b, -5f, 2.2f, -6f), A(b, -4f, 2.6f, -5f), b.position + Vector3.up * 1.2f, b.position + Vector3.up * 1.4f, t, 34f);
            }).events.Add((1.6f, () => CatchReveal.Ensure().Enqueue(Catalog.Get("ship_bell"), true)));

            Add("shop_rush", 6f, () =>
            {
                Clear();
                Hour(11.5f);
                Ashore(shop.position, shop.eulerAngles.y);
                GameState.D.restoration = 1;
                Restoration.I?.Apply();
                GameState.D.stock.Clear();
                foreach (var id in new[] { "herring", "mackerel", "cod", "salmon", "dungeness", "halibut" }) GameState.Add(GameState.D.stock, id, 4);
                ShopCounter.I?.RefreshDisplay();
                ShopCounter.I?.OpenShop();
                ShopCounter.I?.FillQueue(4);
            }, t =>
            {
                var c = shop.position;
                return Dolly(c + new Vector3(4.6f, 1.6f, 4.2f), c + new Vector3(3.9f, 1.4f, 3.4f), c + new Vector3(1.4f, 0.6f, -1.2f), c + new Vector3(1.2f, 0.6f, -1.0f), t, 36f);
            });

            Add("museum", 4.5f, () =>
            {
                if (ShopCounter.I != null && ShopCounter.I.Open) ShopCounter.I.Close();
                Hour(15.5f);
                GameState.D.donated.Clear();
                foreach (var id in new[] { "ship_bell", "brass_compass", "pearl", "diving_helmet", "ammonite", "message_bottle", "porcelain_teapot", "spyglass", "salmon", "herring", "rockfish", "dungeness", "red_king", "lumpsucker" }) GameState.D.donated.Add(id);
                Museum.I?.Refresh();
                if (inkwell != null) Pip.Teleport(A(inkwell, 0f, 0f, 2f), inkwell.eulerAngles.y + 180f);
                inkwell?.GetComponentInChildren<CritterAnimator>()?.Play(Gesture.Point, 2.4f);
            }, t =>
            {
                var c = inkwell != null ? inkwell : R.museumDoor;
                return Dolly(A(c, 3.2f, 1.7f, 4.5f), A(c, 1.6f, 1.5f, 4.2f), c.position + Vector3.up * 1.1f, c.position + Vector3.up * 1.0f, t, 34f);
            });

            Add("shelby", 3.5f, () =>
            {
                Hour(12f);
                shelby?.GetComponentInChildren<CritterAnimator>()?.Play(Gesture.Hop, 1.4f);
                VoiceBlips.I?.Mumble("shelby", "wow!");
            }, t =>
            {
                var c = shelby != null ? shelby : R.museumDoor;
                return Dolly(A(c, 1.2f, 0.7f, 2.4f), A(c, 0.6f, 0.55f, 1.8f), c.position + Vector3.up * 0.35f, c.position + Vector3.up * 0.35f, t, 30f);
            });

            Add("deep_sail", 3.5f, () =>
            {
                Hour(16.2f, (int)Weather.Fog);
                if (DayCycle.I != null) { DayCycle.I.overcast = 0.75f; DayCycle.I.fogBoost = 1.8f; }
                BoatAt(mouth + new Vector3(90, 0, 540), 340f, 6.5f);
            }, t =>
            {
                var b = Boat.transform;
                return Dolly(A(b, 7f, 1.6f, 9f), A(b, 6f, 1.9f, 6f), b.position + Vector3.up * 2.2f, b.position + Vector3.up * 2.2f, t, 34f);
            });

            Add("lanterns_night", 6f, () =>
            {
                Clear();
                Hour(21.3f, (int)Weather.Clear);
                Ashore(R.playerSpawn.position, R.playerSpawn.eulerAngles.y);
                GameState.D.restoration = 3;
                Restoration.I?.Apply();
            }, t => Dolly(mouth + new Vector3(-25, 9, -20), mouth + new Vector3(-12, 7, -32), new Vector3(0, 3, 0), new Vector3(4, 3, -4), t, 34f));

            Add("sunset_home", 7f, () =>
            {
                Hour(18.6f, (int)Weather.Breezy);
                if (DayCycle.I != null) DayCycle.I.fogBoost = 1f;
                BoatAt(mouth + new Vector3(6, 0, 30), 186f, 5f);
            }, t =>
            {
                var b = Boat.transform;
                return Dolly(A(b, -9f, 2.6f, 14f), A(b, -7f, 2.4f, 11f), b.position + Vector3.up * 1.8f, b.position + Vector3.up * 1.8f, t, 34f);
            });

            Add("logo_bg", 6f, () => { Hour(19.1f); BoatAt(mouth + new Vector3(0, 0, -40), 190f, 2.5f); },
                t => Dolly(mouth + new Vector3(30, 18, 30), mouth + new Vector3(26, 16, 24), new Vector3(0, 4, 0), new Vector3(0, 4, -4), t, 36f));
        }

        Shot Add(string name, float dur, Action setup, Func<float, (Vector3, Vector3, float)> camFn)
        {
            var s = new Shot { name = name, dur = dur, setup = setup, cam = camFn };
            shots.Add(s);
            return s;
        }

        // ---------------------------------------------------------------- capture
        IEnumerator Start()
        {
            string dir = CommandLine.Get("-capture", Path.Combine(Application.persistentDataPath, "trailer"));
            Directory.CreateDirectory(dir);
            Settings.Music = 0f;   // the score is laid in by the edit
            Settings.Apply(false);
            yield return null;
            yield return null;
            cam = Camera.main;
            var rig = cam.GetComponent<CameraRig>();
            if (rig != null) rig.enabled = false;
            focus = new GameObject("TrailerFocus").transform;
            var lens = cam.GetComponent<ClayLens>();
            if (lens != null) { lens.focusTarget = focus; lens.focusOffsetY = 0f; }
            HUD.I?.Visible(false);
            GameFlow.ClockRunning = false;
            yield return new WaitForSeconds(1.5f);
            Plan();
            var only = CommandLine.Get("-only");
            var filter = only != null ? new HashSet<string>(only.Split(',')) : null;
            foreach (var s in shots)
            {
                if (filter != null && !filter.Contains(s.name)) continue;
                yield return Film(s, Path.Combine(dir, s.name));
            }
            Application.Quit();
        }

        IEnumerator Film(Shot s, string dir)
        {
            Directory.CreateDirectory(dir);
            Debug.Log("[Trailer] shot " + s.name);
            current = null;
            s.setup?.Invoke();
            // settle: let puppets, puffs and lighting arrive before rolling
            shotT = 0f;
            current = s;
            for (int i = 0; i < 12; i++) yield return null;
            yield return new WaitForSeconds(0.6f);
            shotT = 0f;
            int ev = 0;
            Time.captureDeltaTime = 1f / Fps;
            AudioRenderer.Start();
            var audio = new List<float>();
            int frames = Mathf.RoundToInt(s.dur * Fps);
            for (int f = 0; f < frames; f++)
            {
                float t = f / (float)Fps;
                while (ev < s.events.Count && s.events[ev].t <= t) { s.events[ev].a?.Invoke(); ev++; }
                shotT = t;
                yield return new WaitForEndOfFrame();
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(dir, $"f_{f:00000}.jpg"), tex.EncodeToJPG(94));
                Destroy(tex);
                int n = AudioRenderer.GetSampleCountForCaptureFrame();
                var na = new Unity.Collections.NativeArray<float>(n * 2, Unity.Collections.Allocator.Temp);
                if (AudioRenderer.Render(na)) audio.AddRange(na.ToArray());
                na.Dispose();
            }
            AudioRenderer.Stop();
            Time.captureDeltaTime = 0f;
            WriteWav(Path.Combine(dir, "audio.wav"), audio, AudioSettings.outputSampleRate, 2);
            current = null;
            Clear();
        }

        void LateUpdate()
        {
            if (current == null || cam == null) return;
            float t = Mathf.Clamp01(shotT / current.dur);
            current.tick?.Invoke(t);
            var (pos, look, fov) = current.cam(t);
            cam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(look - pos));
            cam.fieldOfView = fov;
            focus.position = look;
        }

        static void WriteWav(string path, List<float> data, int rate, int ch)
        {
            using var bw = new BinaryWriter(File.Create(path));
            int bytes = data.Count * 2;
            bw.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));
            bw.Write(36 + bytes);
            bw.Write(System.Text.Encoding.ASCII.GetBytes("WAVEfmt "));
            bw.Write(16); bw.Write((short)1); bw.Write((short)ch); bw.Write(rate); bw.Write(rate * ch * 2); bw.Write((short)(ch * 2)); bw.Write((short)16);
            bw.Write(System.Text.Encoding.ASCII.GetBytes("data"));
            bw.Write(bytes);
            foreach (var v in data) bw.Write((short)Mathf.Clamp(v * 32767f, -32768f, 32767f));
        }
    }
}
