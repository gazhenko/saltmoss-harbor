using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The Salty Puffin's counter. Open up and customers (gulls, crabs, seals in hats) walk down the pier, queue, and
    /// ask for something with a speech bubble. Serve it from the ice display: exact orders pay full price plus a tip
    /// (more for today's catch, more with crushed ice); if you're out of it they shrug and wander off — no harm done.
    /// While Pip is at sea, Nell sells a little of the stock at a friendly discount.
    /// </summary>
    public class ShopCounter : Interactable
    {
        public static ShopCounter I { get; private set; }
        public Transform standPoint;            // where Pip stands behind the counter
        public Vector3[] queue = new Vector3[0];
        public Vector3[] path = new Vector3[0]; // spawn -> queue start
        public Transform[] displaySlots = new Transform[0];
        public bool Open { get; private set; }

        readonly List<Customer> customers = new List<Customer>();
        readonly List<GameObject> displayed = new List<GameObject>();
        float spawnTimer;
        int served;

        void Awake() { I = this; }

        void Start()
        {
            GameState.Changed += RefreshDisplay;
            RefreshDisplay();
        }

        void OnDestroy() => GameState.Changed -= RefreshDisplay;

        public override string Prompt => Open ? "Close the shop" : GameState.Count(GameState.D.stock) > 0 ? "Open the shop" : "Open the shop (nothing to sell yet!)";
        public override bool CanInteract(PlayerController p) => !ServeUI.Showing;

        public override void Interact(PlayerController p)
        {
            if (Open) { Close(); return; }
            if (GameState.Count(GameState.D.stock) == 0)
            {
                DialogueRunner.Play("shop_empty", "nell");
                return;
            }
            if (GameState.D.hour >= 21f) { GameState.Say("It's too late — folks are tucked up in bed."); return; }
            OpenShop();
        }

        /// <summary>Open once the conversation that asked for it has finished.</summary>
        public void OpenWhenFree() => StartCoroutine(OpenLater());

        IEnumerator OpenLater()
        {
            while (DialogueRunner.Active) yield return null;
            yield return null;
            OpenShop();
        }

        public void OpenShop()
        {
            Open = true;
            served = 0;
            spawnTimer = 1.5f;
            var p = PlayerController.I;
            if (standPoint != null) p.Teleport(standPoint.position, standPoint.eulerAngles.y);
            PlayerController.LockCount++;
            p.anim.activity = Activity.Serve;
            if (GameFlow.I != null) GameFlow.I.place = GameFlow.Place.Shop;
            AudioDirector.Play("shop_bell", transform.position, 0.9f, 0f);
            if (CameraRig.I != null && standPoint != null)
            {
                var look = standPoint.position + standPoint.forward * 0.9f + Vector3.up * 1.0f;
                var dir = (standPoint.forward * 5.4f + Vector3.up * 1.3f + standPoint.right * 1.8f);
                if (Physics.SphereCast(look, 0.3f, dir.normalized, out var hit, dir.magnitude, 1 << 10, QueryTriggerInteraction.Ignore))
                    dir = dir.normalized * Mathf.Max(2.2f, hit.distance - 0.2f);
                var front = look + dir;
                CameraRig.I.SetOverride(front, Quaternion.LookRotation(look - front), 36f);
            }
            GameState.Say("The Salty Puffin is open! Press " + GameInput.Label(Bind.Interact) + " to serve, " + GameInput.Label(Bind.Journal) + " to close up.");
        }

        public void Close()
        {
            if (!Open) return;
            Open = false;
            foreach (var c in customers) if (c != null) c.Leave(false);
            customers.Clear();
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            PlayerController.I.anim.activity = Activity.None;
            CameraRig.I?.ClearOverride();
            if (GameFlow.I != null) GameFlow.I.place = GameFlow.Place.Town;
            if (served > 0) GameState.Say($"Closed up. Served {served} customer{(served == 1 ? "" : "s")} today!");
        }

        void Update()
        {
            if (!Open) return;
            var D = GameState.D;
            customers.RemoveAll(c => c == null);
            float rate = 9f - D.restoration * 1.6f - (GameState.Has("paint") ? 1f : 0f) - (GameState.Has("bunting") ? 0.5f : 0f);
            spawnTimer -= Time.deltaTime;
            if (spawnTimer <= 0f && customers.Count < Mathf.Min(queue.Length, 3 + D.restoration))
            {
                spawnTimer = Random.Range(rate * 0.7f, rate * 1.3f);
                if (D.hour < 21f) Spawn();
            }
            // queue order
            for (int i = 0; i < customers.Count; i++) customers[i].SetQueueSpot(i < queue.Length ? queue[i] : queue[queue.Length - 1], i == 0);
            var front = customers.Count > 0 ? customers[0] : null;
            if (front != null && front.AtCounter && !ServeUI.Showing && !DialogueRunner.Active)
            {
                HUD.ActionPrompt = $"Serve the {front.Species}";
                HUD.ActionKey = "Interact";
                if (GameInput.Interact.WasPressedThisFrame()) ServeUI.Open(front, (id) => Serve(front, id));
            }
            if (GameInput.Journal.WasPressedThisFrame() && !ServeUI.Showing) Close();
            if (GameState.Count(D.stock) == 0 && customers.Count == 0) { GameState.Say("Sold out! Time to go fishing."); Close(); }
            if (D.hour >= 21.5f) Close();
        }

        /// <summary>Cut-scenes: fill the queue straight away (no walk down the pier).</summary>
        public void FillQueue(int n)
        {
            for (int i = 0; i < n && i < queue.Length; i++)
            {
                var c = Customer.Create(path, this);
                if (c == null) return;
                c.WarpTo(queue[i]);
                customers.Add(c);
            }
        }

        void Spawn()
        {
            if (path.Length == 0 || queue.Length == 0) return;
            var c = Customer.Create(path, this);
            if (c != null) customers.Add(c);
        }

        void Serve(Customer c, string itemId)
        {
            if (itemId == null) { c.Leave(false); customers.Remove(c); return; }
            var def = Catalog.Get(itemId);
            int have = GameState.Count(GameState.D.stock, itemId);
            int n = Mathf.Min(have, c.Count);
            bool exact = itemId == c.Wants && n == c.Count;
            int fresh = GameState.Remove(GameState.D.stock, itemId, n);
            float mult = GameState.Has("ice") ? 1.15f : 1f;
            int pay = Mathf.RoundToInt(def.price * n * mult * (exact ? 1f : 0.7f));
            int tip = exact ? Mathf.RoundToInt(def.price * 0.1f * n + fresh * 3) : 0;
            GameState.Earn(pay + tip);
            GameState.D.customersServed++;
            served++;
            AudioDirector.UI("register", 0.8f);
            AudioDirector.UI("coin", 0.6f);
            AudioDirector.I?.Jingle("jingle_sale", 0.6f);
            GameState.Say(exact ? $"+{pay} SD{(tip > 0 ? $" and a {tip} SD tip" : "")}! The {c.Species} looks delighted." : $"+{pay} SD. Not quite what they wanted, but they'll take it.");
            c.Leave(exact);
            customers.Remove(c);
            if (!GameState.Flag("first_sale")) GameState.SetFlag("first_sale");
            Restoration.Check();
        }

        /// <summary>Fish on the ice display: one model per tray, best-stocked first.</summary>
        public void RefreshDisplay()
        {
            if (displaySlots.Length == 0) return;
            var stock = new List<Stack>(GameState.D.stock);
            stock.Sort((a, b) => b.count.CompareTo(a.count));
            var ids = new List<string>();
            foreach (var s in stock) if (!ids.Contains(s.id)) ids.Add(s.id);
            int slots = Mathf.Min(displaySlots.Length, GameState.DisplaySlots);
            while (displayed.Count < displaySlots.Length) displayed.Add(null);
            for (int i = 0; i < displaySlots.Length; i++)
            {
                string want = i < slots && i < ids.Count ? ids[i] : null;
                var cur = displayed[i];
                if (cur != null && (want == null || cur.name != Catalog.Get(want).model)) { Destroy(cur); displayed[i] = null; }
                if (want != null && displayed[i] == null && displaySlots[i] != null)
                {
                    var def = Catalog.Get(want);
                    var go = ModelBank.I.Spawn(def.model, displaySlots[i].position, displaySlots[i].rotation * Quaternion.Euler(0, 90, 0), displaySlots[i]);
                    float size = go.GetComponent<ClayModel>()?.VisualBounds().size.magnitude ?? 0.5f;
                    if (size > 0.7f) go.transform.localScale = Vector3.one * (0.7f / size);
                    go.name = def.model;
                    displayed[i] = go;
                }
            }
        }

        /// <summary>Nell minds the counter while Pip's away: a share of the stock sells each in-game hour, 80% price.</summary>
        public static void NellSales(float hours)
        {
            var D = GameState.D;
            if (D.stock.Count == 0 || hours <= 0f) return;
            float share = Mathf.Clamp01(0.06f * hours);
            int earned = 0, sold = 0;
            foreach (var s in D.stock.ToArray())
            {
                int n = Mathf.FloorToInt(s.count * share + Random.value * 0.6f);
                if (n <= 0) continue;
                var def = Catalog.Get(s.id);
                GameState.Remove(D.stock, s.id, n);
                earned += Mathf.RoundToInt(def.price * n * 0.8f);
                sold += n;
            }
            if (earned > 0)
            {
                GameState.Earn(earned);
                GameState.Say($"Nell sold {sold} at the counter while you were out: +{earned} SD");
            }
        }
    }
}
