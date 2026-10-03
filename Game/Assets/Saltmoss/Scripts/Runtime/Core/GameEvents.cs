using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// Handlers for the small !event hooks used by dialogue scripts: the forecast, letters, junk, sleeping, the
    /// restoration ceremony, Shelby's errands. (Big ones — shops, museum — live with their UIs.)
    /// </summary>
    public static class GameEvents
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Register()
        {
            var V = DialogueRunner.Vars;
            GameFlow.On("forecast", (a, done) =>
            {
                var D = GameState.D;
                V["today"] = GameFlow.WeatherName(D.weather).ToLowerInvariant();
                V["tomorrow"] = GameFlow.WeatherName(D.forecast).ToLowerInvariant();
                V["sea"] = D.weather >= (int)Weather.Storm ? "a proper storm out in the Deep — rogue waves, ice, the lot" :
                           D.weather >= (int)Weather.Squalls ? "squalls past the kelp. Watch for rogue waves" :
                           D.weather == (int)Weather.Fog ? "fog on the water. Mind the rocks, and the ice in the Deep" :
                           D.weather == (int)Weather.Showers ? "a bit of rain, nothing to fret about" : "a calm sea, flat as a pancake";
                done();
            });
            GameFlow.On("letters", (a, done) =>
            {
                string r = Letters.DeliverAll();
                V["letters"] = r ?? "";
                V["orders"] = Letters.Open().Count.ToString();
                if (r != null) { AudioDirector.UI("stamp"); AudioDirector.UI("coin"); }
                done();
            });
            GameFlow.On("new_letter", (a, done) => { Letters.NewOrder(); done(); });
            GameFlow.On("sell_junk", (a, done) =>
            {
                var D = GameState.D;
                int n = 0, pay = 0;
                foreach (var s in D.pocket.ToArray())
                {
                    var def = Catalog.Get(s.id);
                    if (def == null || def.kind != Kind.Junk) continue;
                    n += s.count;
                    pay += def.price * s.count;
                    GameState.Remove(D.pocket, s.id, s.count);
                }
                V["junk"] = n.ToString();
                V["junkpay"] = pay.ToString();
                if (pay > 0) { GameState.Earn(pay, false); AudioDirector.UI("coin"); }
                done();
            });
            GameFlow.On("sell_dupes", (a, done) =>
            {
                // the professor buys treasures the museum already has, for his "lending library"
                var D = GameState.D;
                int pay = 0, n = 0;
                foreach (var s in D.pocket.ToArray())
                {
                    var def = Catalog.Get(s.id);
                    if (def == null || def.kind != Kind.Treasure || !D.donated.Contains(s.id)) continue;
                    pay += def.price * s.count;
                    n += s.count;
                    GameState.Remove(D.pocket, s.id, s.count);
                }
                V["dupes"] = n.ToString();
                V["dupepay"] = pay.ToString();
                if (pay > 0) { GameState.Earn(pay); AudioDirector.UI("register"); }
                done();
            });
            GameFlow.On("ceremony", (a, done) => { Restoration.Advance(); done(); });
            GameFlow.On("restoration", (a, done) => { V["progress"] = Restoration.Progress().Replace("\n", " — "); done(); });
            GameFlow.On("sleep", (a, done) => GameFlow.Sleep(done));
            GameFlow.On("save", (a, done) => { GameState.Save(); GameState.Say("Saved."); done(); });
            GameFlow.On("open_shop", (a, done) => { done(); ShopCounter.I?.OpenWhenFree(); });
        }
    }

    /// <summary>The night passes: fade to a starry clay card, tick to morning, wake at Pip's door.</summary>
    public class SleepFade : MonoBehaviour
    {
        static SleepFade inst;
        CanvasGroup g;
        TMPro.TextMeshProUGUI text;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (inst != null) return;
            var go = new GameObject("SleepFade");
            Object.DontDestroyOnLoad(go);
            inst = go.AddComponent<SleepFade>();
            var c = ClayUI.Canvas("SleepCanvas", 90, go.transform);
            inst.g = c.gameObject.AddComponent<CanvasGroup>();
            inst.g.alpha = 0f;
            inst.g.blocksRaycasts = false;
            var bg = ClayUI.Fill("Night", c.transform);
            bg.gameObject.AddComponent<Image>().color = new Color(0.08f, 0.1f, 0.2f, 1f);
            inst.text = ClayUI.Text("Text", c.transform, "", 64f, ClayUI.Cream, TMPro.TextAlignmentOptions.Center, true);
            GameFlow.SleepRequested += done => inst.StartCoroutine(inst.Run(done));
        }

        IEnumerator Run(System.Action done)
        {
            PlayerController.LockCount++;
            GameFlow.ClockRunning = false;
            ShopCounter.I?.Close();
            text.text = "Zzz…";
            for (float t = 0; t < 1f; t += Time.unscaledDeltaTime / 0.8f) { g.alpha = t; yield return null; }
            g.alpha = 1f;
            // finish the day: Nell sells a little overnight, pots keep soaking
            var boat = BoatController.I;
            if (boat != null && !boat.Docked)
            {
                // Walter tows the Sally Mae home
                boat.ForceDock();
                BoatController.Unload();
                GameState.Say("Walter towed the Sally Mae home for you overnight.");
            }
            GameFlow.NewDay();
            yield return new WaitForSecondsRealtime(0.6f);
            text.text = $"Day {GameState.D.day}";
            var p = PlayerController.I;
            var home = WorldRefs.I != null ? WorldRefs.I.pipDoor : null;
            if (p != null)
            {
                if (p.Aboard) p.Disembark(home != null ? home.position : p.transform.position, home != null ? home.eulerAngles.y : 0f);
                else if (home != null) p.Teleport(home.position, home.eulerAngles.y);
                if (CameraRig.I != null) { CameraRig.I.target = p.transform; CameraRig.I.boatMode = false; CameraRig.I.distance = 7.5f; CameraRig.I.pivotHeight = 1f; CameraRig.I.SnapBehindTarget(); }
            }
            if (GameFlow.I != null) GameFlow.I.place = GameFlow.Place.Town;
            yield return new WaitForSecondsRealtime(1.2f);
            for (float t = 1; t > 0f; t -= Time.unscaledDeltaTime / 0.8f) { g.alpha = t; yield return null; }
            g.alpha = 0f;
            GameFlow.ClockRunning = true;
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            done?.Invoke();
        }
    }
}
