using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Crab pots stacked on the Sally Mae's deck: one at each pot slot for every pot still aboard.</summary>
    public class PotsVisual : MonoBehaviour
    {
        static PotsVisual inst;
        readonly List<GameObject> pots = new List<GameObject>();

        void Awake() { inst = this; }
        void Start() => Refresh();

        public static void Refresh()
        {
            if (inst == null || BoatController.I == null) return;
            var boat = BoatController.I;
            int want = CrabPots.OnDeck;
            for (int i = 0; i < boat.potSlots.Length; i++)
            {
                while (inst.pots.Count <= i) inst.pots.Add(null);
                bool on = i < want;
                if (on && inst.pots[i] == null && boat.potSlots[i] != null)
                {
                    var s = boat.potSlots[i];
                    inst.pots[i] = ModelBank.I.Spawn("boat/crab_pot", s.position, s.rotation, s);
                }
                if (inst.pots[i] != null) inst.pots[i].SetActive(on);
            }
        }
    }

    /// <summary>The haul tumbles onto the deck — little clay crabs scuttle about for a moment, then go below.</summary>
    public class DeckCatch : MonoBehaviour
    {
        float life;
        Vector3 vel;
        Transform deck;

        public static void Spill(BoatController boat, Dictionary<string, int> tally)
        {
            if (boat == null) return;
            var deckT = boat.puppet != null ? boat.puppet.transform : boat.transform;
            int k = 0;
            foreach (var kv in tally)
                for (int i = 0; i < Mathf.Min(kv.Value, 4); i++, k++)
                {
                    var def = Catalog.Get(kv.Key);
                    var local = new Vector3(Random.Range(-1.1f, 1.1f), 0.95f + 0.05f * k, Random.Range(-2.2f, -0.4f));
                    var go = ModelBank.I.Spawn(def.model, deckT.TransformPoint(local), deckT.rotation * Quaternion.Euler(0, Random.Range(0, 360f), 0), deckT);
                    var dc = go.AddComponent<DeckCatch>();
                    dc.life = 3.5f + Random.value * 1.5f;
                    dc.deck = deckT;
                    dc.vel = new Vector3(Random.Range(-0.6f, 0.6f), 0f, Random.Range(-0.6f, 0.6f));
                }
        }

        void Update()
        {
            if (!ClayClock.SteppedThisFrame) return;
            life -= ClayClock.StepDt;
            transform.localPosition += vel * ClayClock.StepDt;
            transform.localRotation *= Quaternion.Euler(0f, Random.Range(-25f, 25f), 0f);
            if (life < 0.6f) transform.localScale *= 0.7f;
            if (life <= 0f) Destroy(gameObject);
        }
    }
}
