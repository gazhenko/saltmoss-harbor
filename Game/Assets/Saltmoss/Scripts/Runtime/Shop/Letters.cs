using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Special orders by post: folk from up and down the coast write in (via Marge) asking for a particular catch.
    /// Bring it to the post office before the day they name and they pay handsomely. Late? They still pay — a bit less,
    /// with a kind note.
    /// </summary>
    public static class Letters
    {
        public class Order
        {
            public string item, from;
            public int count, reward, due;
            public string Encode() => $"{item}|{count}|{reward}|{due}|{from}";
            public static Order Decode(string s)
            {
                var p = s.Split('|');
                return new Order { item = p[0], count = int.Parse(p[1]), reward = int.Parse(p[2]), due = int.Parse(p[3]), from = p.Length > 4 ? p[4] : "a friend" };
            }
            public ItemDef Def => Catalog.Get(item);
            public string Line => $"{from}: {count} × {Def?.name} by day {due} — {reward} SD";
        }

        static readonly string[] Senders =
        {
            "Mrs. Puffinsworth of Gullhaven", "The Cormorant Inn, Brinecliff", "Captain Tern (retired)", "The Otter Twins' chowder stall",
            "Old Mother Eider", "Lighthouse keeper at Skerry Point", "The Gannet & Gherkin restaurant", "Little Kittiwake's birthday party",
        };

        public static List<Order> Open()
        {
            var list = new List<Order>();
            foreach (var s in GameState.D.letters) list.Add(Order.Decode(s));
            return list;
        }

        public static void NewOrder()
        {
            var D = GameState.D;
            if (D.letters.Count >= 3) return;
            var pool = new List<ItemDef>();
            foreach (var d in Catalog.All)
                if (d.Sellable && !d.legendary && (D.discovered.Contains(d.id) || (d.zones & ZoneMask.Shallows) != 0)) pool.Add(d);
            if (pool.Count == 0) return;
            var r = new System.Random(D.day * 101 + D.letters.Count);
            var def = pool[r.Next(pool.Count)];
            int count = def.price > 100 ? 1 : def.price > 40 ? r.Next(1, 3) : r.Next(2, 5);
            var o = new Order { item = def.id, count = count, reward = Mathf.RoundToInt(def.price * count * 1.8f + 40), due = D.day + 2 + r.Next(2), from = Senders[r.Next(Senders.Length)] };
            D.letters.Add(o.Encode());
            GameState.Notify();
            GameState.Say($"A letter at the post office! {o.from} wants {o.count} {o.Def.name}.");
        }

        /// <summary>Sends off every order that can be filled from the cold store and the hold. Returns a summary line.</summary>
        public static string DeliverAll()
        {
            var D = GameState.D;
            int paid = 0, sent = 0;
            var keep = new List<string>();
            foreach (var s in D.letters)
            {
                var o = Order.Decode(s);
                int have = GameState.Count(D.stock, o.item) + GameState.Count(D.hold, o.item);
                if (have < o.count) { keep.Add(s); continue; }
                int need = o.count;
                int fromStock = Mathf.Min(need, GameState.Count(D.stock, o.item));
                if (fromStock > 0) GameState.Remove(D.stock, o.item, fromStock);
                if (need - fromStock > 0) GameState.Remove(D.hold, o.item, need - fromStock);
                int pay = D.day <= o.due ? o.reward : Mathf.RoundToInt(o.reward * 0.7f);
                paid += pay;
                sent++;
            }
            D.letters = keep;
            if (sent == 0) return null;
            GameState.Earn(paid);
            Restoration.Check();
            return $"{sent} parcel{(sent > 1 ? "s" : "")} sent! +{paid} SD";
        }
    }
}
