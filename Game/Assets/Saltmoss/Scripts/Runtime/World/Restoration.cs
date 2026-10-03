using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Bringing Saltmoss Harbor back to life, in three steps: the lanterns relit, fresh paint and bunting, and the
    /// lighthouse lit again. Each needs sales and museum donations, ends with a little ceremony on the pier, and
    /// visibly changes the town (objects tagged tier1/tier2/tier3 appear, "shabby" ones go).
    /// </summary>
    public class Restoration : MonoBehaviour
    {
        public static Restoration I { get; private set; }
        public static readonly int[] SalesNeeded = { 0, 500, 2200, 5500 };
        public static readonly int[] DonationsNeeded = { 0, 3, 8, 14 };
        public static readonly string[] Names = { "", "The Lanterns Relit", "Fresh Paint on the Pier", "The Lighthouse Shines" };

        public readonly List<GameObject> tier1 = new List<GameObject>(), tier2 = new List<GameObject>(), tier3 = new List<GameObject>(), shabby = new List<GameObject>();
        public List<Light> lanternLights = new List<Light>();
        public Light lighthouse;

        void Awake() { I = this; }
        void Start() => Apply();

        public static int Next => Mathf.Min(GameState.D.restoration + 1, 3);

        public static bool Ready()
        {
            var D = GameState.D;
            if (D.restoration >= 3) return false;
            int n = D.restoration + 1;
            return D.totalSales >= SalesNeeded[n] && D.donated.Count >= DonationsNeeded[n];
        }

        /// <summary>Called after sales and donations: queues the ceremony for the next calm moment in town.</summary>
        public static void Check()
        {
            if (Ready() && !GameState.Flag("ceremony_pending"))
            {
                GameState.SetFlag("ceremony_pending");
                GameState.Say("Walter wants a word on the pier! Something about the harbour…");
            }
        }

        public static string Progress()
        {
            var D = GameState.D;
            if (D.restoration >= 3) return "Saltmoss Harbor is shining again! Keep fishing, keep collecting.";
            int n = D.restoration + 1;
            return $"<b>{Names[n]}</b>\nSold {Mathf.Min(D.totalSales, SalesNeeded[n]):N0}/{SalesNeeded[n]:N0} SD · Donated {Mathf.Min(D.donated.Count, DonationsNeeded[n])}/{DonationsNeeded[n]}";
        }

        /// <summary>The ceremony's finale: bump the tier and change the town.</summary>
        public static void Advance()
        {
            var D = GameState.D;
            if (D.restoration >= 3) return;
            D.restoration++;
            D.flags.Remove("ceremony_pending");
            GameState.Notify();
            AudioDirector.I?.Jingle("jingle_restoration");
            I?.Apply();
            HUD.I?.Banner(Names[D.restoration].ToUpperInvariant(), "Saltmoss Harbor is coming back to life");
            GameState.Save();
        }

        public void Apply()
        {
            int r = GameState.D.restoration;
            foreach (var g in tier1) if (g) g.SetActive(r >= 1);
            foreach (var g in tier2) if (g) g.SetActive(r >= 2);
            foreach (var g in tier3) if (g) g.SetActive(r >= 3);
            foreach (var g in shabby) if (g) g.SetActive(r < 2);
            for (int i = 0; i < lanternLights.Count; i++)
                if (lanternLights[i]) lanternLights[i].gameObject.SetActive(r >= 1 || GameState.Has("lanterns") || i % 3 == 0);
            if (lighthouse) lighthouse.gameObject.SetActive(r >= 3);
        }

        void Update()
        {
            // lamp lights follow the night glow; the lighthouse beam sweeps
            float glow = DayCycle.I != null ? DayCycle.I.NightGlow : 0f;
            foreach (var l in lanternLights) if (l && l.gameObject.activeSelf) l.intensity = Mathf.Lerp(0f, 2.2f, glow) * (0.95f + Mathf.PerlinNoise(Time.time * 3f, l.GetInstanceID()) * 0.1f);
            if (lighthouse && lighthouse.gameObject.activeSelf)
            {
                lighthouse.intensity = Mathf.Lerp(0.5f, 9f, glow);
                if (ClayClock.SteppedThisFrame) lighthouse.transform.rotation = Quaternion.Euler(4f, ClayClock.StepTime * 40f, 0f);
            }
        }
    }
}
