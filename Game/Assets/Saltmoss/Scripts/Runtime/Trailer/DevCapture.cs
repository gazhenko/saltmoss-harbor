using System.Collections;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Saltmoss
{
    /// <summary>
    /// Command-line verification captures for builds:
    ///   -scene Gallery                    load a scene directly
    ///   -cam px,py,pz,tx,ty,tz[,fov]      fixed camera pose looking at a target (sets the focus distance too)
    ///   -hour 16.5 -overcast 0.3 -storm 0  lighting / weather overrides
    ///   -motion 0|12|24 -film              stop-motion overrides
    ///   -shots dir -shotTimes 2,4,6        write screenshots at those (real) seconds, then quit
    ///   -record dir -recordSec 4 -recordFps 30 -recordDelay 1  fixed-timestep frame sequence, then quit
    ///   -quitAfter 120                    safety
    /// </summary>
    public class DevCapture : MonoBehaviour
    {
        static DevCapture _i;
        public static bool Active => _i != null;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (_i != null) return;
            bool any = CommandLine.Has("-shots") || CommandLine.Has("-scene") || CommandLine.Has("-record") || CommandLine.Has("-cam") || CommandLine.Has("-play");
            if (!any) return;
            var g = new GameObject("DevCapture");
            DontDestroyOnLoad(g);
            _i = g.AddComponent<DevCapture>();
        }

        static float F(string s) => float.Parse(s, CultureInfo.InvariantCulture);

        IEnumerator Start()
        {
            Invoke(nameof(Bail), CommandLine.GetFloat("-quitAfter", 150f));
            string scene = CommandLine.Get("-scene");
            if (scene != null && SceneManager.GetActiveScene().name != scene)
            {
                SceneManager.LoadScene(scene);
                yield return null;
                yield return null;
            }
            ApplyOverrides();
            yield return null;
            Scenario();
            string rec = CommandLine.Get("-record");
            if (rec != null)
            {
                Directory.CreateDirectory(rec);
                int fps = (int)CommandLine.GetFloat("-recordFps", 30);
                float secs = CommandLine.GetFloat("-recordSec", 4f);
                yield return new WaitForSecondsRealtime(CommandLine.GetFloat("-recordDelay", 1.5f));
                Time.captureDeltaTime = 1f / fps;
                int frames = Mathf.RoundToInt(secs * fps);
                for (int f = 0; f < frames; f++)
                {
                    yield return new WaitForEndOfFrame();
                    var tex = ScreenCapture.CaptureScreenshotAsTexture();
                    File.WriteAllBytes(Path.Combine(rec, $"f_{f:00000}.jpg"), tex.EncodeToJPG(92));
                    Destroy(tex);
                }
                Time.captureDeltaTime = 0f;
                Application.Quit();
                yield break;
            }
            string dir = CommandLine.Get("-shots");
            if (dir != null)
            {
                Directory.CreateDirectory(dir);
                float start = Time.unscaledTime;
                int n = 0;
                foreach (var s in CommandLine.Get("-shotTimes", "3,6").Split(','))
                {
                    float t = F(s);
                    while (Time.unscaledTime - start < t) yield return null;
                    yield return new WaitForEndOfFrame();
                    ScreenCapture.CaptureScreenshot(Path.Combine(dir, $"shot_{n++:00}_{SceneManager.GetActiveScene().name}.png"));
                    yield return null;
                }
                yield return new WaitForSecondsRealtime(0.6f);
                Application.Quit();
            }
        }

        /// <summary>
        /// Verification scenarios: -dialogue node[,partner] · -boatAt x,z,yaw[,speed] (Pip aboard) · -catch itemId ·
        /// -openShop · -journal · -stock id:n,id:n · -donated a,b,c · -pots n (dropped around the boat)
        /// </summary>
        void Scenario()
        {
            var D = GameState.D;
            string stock = CommandLine.Get("-stock");
            if (stock != null)
                foreach (var kv in stock.Split(','))
                {
                    var p = kv.Split(':');
                    GameState.Add(D.stock, p[0], p.Length > 1 ? int.Parse(p[1]) : 3);
                }
            string don = CommandLine.Get("-donated");
            if (don != null) { foreach (var id in don.Split(',')) if (!D.donated.Contains(id)) D.donated.Add(id); Museum.I?.Refresh(); }
            ShopCounter.I?.RefreshDisplay();
            string boat = CommandLine.Get("-boatAt");
            if (boat != null && BoatController.I != null)
            {
                var f = System.Array.ConvertAll(boat.Split(','), F);
                var b = BoatController.I;
                b.Board();
                b.transform.SetPositionAndRotation(new Vector3(f[0], 0f, f[1]), Quaternion.Euler(0f, f.Length > 2 ? f[2] : 0f, 0f));
                if (f.Length > 3) { b.autopilot = true; b.autoSpeed = f[3]; }
                b.puppet?.Snap();
                CameraRig.I?.SnapBehindTarget();
            }
            if (CommandLine.Has("-atBoard") && BoatController.I != null)
            {
                // stand Pip on the floating dock by the Sally Mae, ready to board
                PlayerController.I?.Teleport(BoatController.I.boardPoint, BoatController.I.boardYaw);
                CameraRig.I?.SnapBehindTarget();
            }
            string glyphs = CommandLine.Get("-padGlyphs");
            if (glyphs != null) GameInput.PinPadGlyphs(glyphs == "ps" ? PadStyle.PlayStation : glyphs == "nintendo" ? PadStyle.Nintendo : PadStyle.Xbox);
            int pots = (int)CommandLine.GetFloat("-pots", 0);
            if (pots > 0 && BoatController.I != null)
            {
                var c = BoatController.I.transform.position;
                for (int i = 0; i < pots; i++)
                {
                    var p = c + Quaternion.Euler(0, i * 360f / pots, 0) * Vector3.forward * 14f;
                    D.pots.Add(new PotState { x = p.x, z = p.z, droppedAt = GameState.AbsMinutes - 200f, zone = (int)BoatController.I.ZoneAt(p), colour = i });
                }
                CrabPots.I?.Resync();
                PotsVisual.Refresh();
            }
            string map = CommandLine.Get("-map");
            if (map != null) MapUI.OpenForCapture(map == "sea");
            string dlg = CommandLine.Get("-dialogue");
            if (dlg != null)
            {
                var p = dlg.Split(',');
                var partner = p.Length > 1 ? p[1] : null;
                var w = DialogueRunner.Actor(partner);
                if (w != null && PlayerController.I != null)
                {
                    var spot = w.root.position + w.root.forward * 2f;
                    PlayerController.I.Teleport(spot, Quaternion.LookRotation(w.root.position - spot).eulerAngles.y);
                }
                DialogueRunner.Play(p[0], partner);
            }
            string cat = CommandLine.Get("-catch");
            if (cat != null) CatchReveal.Ensure().Enqueue(Catalog.Get(cat), true);
            if (CommandLine.Has("-openShop")) ShopCounter.I?.OpenShop();
            if (CommandLine.Has("-journal")) JournalUI.Toggle();
        }

        void ApplyOverrides()
        {
            if (CommandLine.Has("-motion"))
            {
                int m = (int)CommandLine.GetFloat("-motion", 12);
                Settings.Motion = m == 0 ? StopMotion.Off : m == 24 ? StopMotion.Ones : StopMotion.Twos;
            }
            if (CommandLine.Has("-film")) Settings.FilmCamera = true;
            Settings.Apply(false);
            var dc = DayCycle.I;
            if (dc != null)
            {
                if (CommandLine.Has("-hour")) { dc.hour = CommandLine.GetFloat("-hour", dc.hour); dc.frozen = true; }
                dc.overcast = CommandLine.GetFloat("-overcast", dc.overcast);
                dc.storm = CommandLine.GetFloat("-storm", dc.storm);
            }
            if (SeaState.I != null && CommandLine.Has("-storm")) SeaState.I.storm = CommandLine.GetFloat("-storm", 0f);
        }

        void LateUpdate()
        {
            string spec = CommandLine.Get("-cam");
            if (spec == null || Camera.main == null) return;
            var f = System.Array.ConvertAll(spec.Split(','), F);
            var cam = Camera.main;
            foreach (var mb in cam.GetComponents<MonoBehaviour>())
                if (mb is CameraRig) mb.enabled = false;
            var p = new Vector3(f[0], f[1], f[2]);
            var t = new Vector3(f[3], f[4], f[5]);
            cam.transform.SetPositionAndRotation(p, Quaternion.LookRotation(t - p));
            if (f.Length > 6) cam.fieldOfView = f[6];
            var lens = cam.GetComponent<ClayLens>();
            if (lens != null)
            {
                if (lens.focusTarget == null || lens.focusTarget.name != "DevFocus")
                {
                    var ft = new GameObject("DevFocus").transform;
                    lens.focusTarget = ft;
                    lens.focusOffsetY = 0f;
                }
                lens.focusTarget.position = t;
            }
        }

        void Bail() { Debug.LogWarning("[DevCapture] -quitAfter reached"); Application.Quit(); }
    }
}
