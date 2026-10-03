using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// A shopper: a gull, crab or seal puppet in a randomly chosen hat who walks down the pier, queues, asks for
    /// something in a speech bubble, and toddles off happy (or with a philosophical shrug).
    /// </summary>
    public class Customer : MonoBehaviour
    {
        static readonly string[] Models = { "chars/cust_gull", "chars/cust_gull_b", "chars/cust_crab", "chars/cust_crab_b", "chars/cust_seal", "chars/cust_seal_b" };

        public string Wants { get; private set; }
        public int Count { get; private set; }
        public string Species { get; private set; }
        public string Voice { get; private set; }
        public bool AtCounter { get; private set; }

        Vector3[] path;
        int pathIdx;
        Vector3 spot;
        bool leaving, happy, front, asked;
        CritterAnimator anim;
        FaceRig face;
        BubbleText.Bubble bubble;
        float speed = 1.3f;

        public static Customer Create(Vector3[] path, ShopCounter shop)
        {
            var ids = new List<string>();
            foreach (var m in Models) if (ModelBank.I.Get(m) != null) ids.Add(m);
            if (ids.Count == 0) return null;
            string id = ids[Random.Range(0, ids.Count)];
            var root = new GameObject("Customer").transform;
            root.position = path[0];
            var vis = new GameObject("Visual").transform;
            vis.SetParent(root, false);
            vis.gameObject.AddComponent<ClayPuppet>();
            var model = ModelBank.I.Spawn(id, root.position, root.rotation, vis);
            var cm = model.GetComponent<ClayModel>();
            // a random hat or scarf
            var acc = new List<string>();
            if (cm != null) foreach (var p in cm.AllPieces) if (p.name.StartsWith("acc_")) acc.Add(p.name);
            if (acc.Count > 0 && Random.value < 0.8f) cm.Show(acc[Random.Range(0, acc.Count)], true);
            var c = root.gameObject.AddComponent<Customer>();
            c.path = path;
            c.anim = model.AddComponent<CritterAnimator>();
            c.anim.model = cm;
            c.anim.Bind();
            c.face = model.AddComponent<FaceRig>();
            c.face.model = cm;
            c.face.Bind();
            c.Species = id.Contains("gull") ? "gull" : id.Contains("crab") ? "crab" : "seal";
            c.Voice = c.Species;
            c.speed = c.Species == "crab" ? 1.6f : c.Species == "seal" ? 1.0f : 1.3f;
            c.PickOrder();
            return c;
        }

        void PickOrder()
        {
            var stock = GameState.D.stock;
            if (stock.Count > 0 && Random.value < 0.8f)
            {
                int total = GameState.Count(stock);
                int r = Random.Range(0, total);
                foreach (var s in stock) { r -= s.count; if (r < 0) { Wants = s.id; break; } }
            }
            if (Wants == null)
            {
                var pool = new List<ItemDef>();
                foreach (var d in Catalog.All) if (d.Sellable && (GameState.D.discovered.Contains(d.id) || (d.zones & ZoneMask.Shallows) != 0)) pool.Add(d);
                Wants = pool[Random.Range(0, pool.Count)].id;
            }
            float x = Random.value;
            Count = x < 0.6f ? 1 : x < 0.9f ? 2 : 3;
            int have = GameState.Count(stock, Wants);
            if (have > 0) Count = Mathf.Min(Count, Mathf.Max(1, have));
        }

        /// <summary>Skip the walk: stand at a queue spot facing the counter.</summary>
        public void WarpTo(Vector3 spot)
        {
            pathIdx = path.Length;
            transform.position = spot;
            var shop = ShopCounter.I;
            if (shop != null && shop.standPoint != null)
            {
                var d = shop.standPoint.position - spot;
                d.y = 0f;
                if (d.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(d);
            }
            GetComponentInChildren<ClayPuppet>()?.Snap();
        }

        public void SetQueueSpot(Vector3 p, bool isFront)
        {
            spot = p;
            front = isFront;
        }

        public void Leave(bool wasHappy)
        {
            if (leaving) return;
            leaving = true;
            happy = wasHappy;
            AtCounter = false;
            bubble?.Close();
            face.expression = wasHappy ? Expr.Happy : Expr.Worried;
            if (wasHappy) { anim.Play(Gesture.Hop, 0.8f); BubbleText.Show(transform.position + Vector3.up * 1.6f, "♥", 1.4f); VoiceBlips.I?.Mumble(Voice, "ooh!"); }
            else { anim.Play(Gesture.Shrug, 1f); VoiceBlips.I?.Mumble(Voice, "hm-mm"); }
            pathIdx = path.Length - 1;
        }

        void Update()
        {
            Vector3 target;
            float dt = Time.deltaTime;
            if (leaving)
            {
                if (pathIdx < 0) { Destroy(gameObject); return; }
                target = path[pathIdx];
                if (Flat(target - transform.position) < 0.3f) { pathIdx--; return; }
            }
            else if (pathIdx < path.Length)
            {
                target = path[pathIdx];
                if (Flat(target - transform.position) < 0.3f) { pathIdx++; return; }
            }
            else target = spot;
            var d = target - transform.position;
            d.y = 0f;
            float dist = d.magnitude;
            float v = dist > 0.08f ? Mathf.Min(speed, dist * 3f) : 0f;
            if (dist > 0.05f)
            {
                transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(d), 300f * dt);
                transform.position += d.normalized * v * dt;
            }
            // follow the deck height
            if (Physics.Raycast(transform.position + Vector3.up * 1.2f, Vector3.down, out var hit, 3f, 1 << 10))
                transform.position = new Vector3(transform.position.x, hit.point.y, transform.position.z);
            anim.speed = v;
            bool arrived = !leaving && pathIdx >= path.Length && dist < 0.15f;
            if (arrived && front)
            {
                AtCounter = true;
                var shop = ShopCounter.I;
                if (shop != null && shop.standPoint != null)
                {
                    var look = shop.standPoint.position - transform.position;
                    look.y = 0f;
                    if (look.sqrMagnitude > 0.01f) transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(look), 300f * dt);
                    face.lookTarget = PlayerController.I != null ? PlayerController.I.transform : null;
                }
                if (!asked)
                {
                    asked = true;
                    VoiceBlips.I?.Mumble(Voice);
                    face.Bounce();
                    var icon = ItemStage.Ensure().Icon(Wants);
                    bubble = BubbleText.Show(Vector3.zero, "×" + Count, 9999f, icon, transform, Vector3.up * HeightOf());
                }
            }
        }

        float HeightOf()
        {
            var m = GetComponentInChildren<ClayModel>();
            return m != null ? m.VisualBounds().size.y + 0.25f : 1.4f;
        }

        static float Flat(Vector3 v) { v.y = 0f; return v.magnitude; }
    }
}
