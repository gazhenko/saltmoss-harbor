using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    public enum Kind { Fish, Crab, Treasure, Junk }
    public enum Zone { Shallows = 0, Kelp = 1, Deep = 2 }
    public enum ShadowSize { Tiny, Small, Medium, Large, Huge, Long }

    [System.Flags]
    public enum ZoneMask { Shallows = 1, Kelp = 2, Deep = 4, All = 7 }

    /// <summary>Everything that can be caught, hauled or dredged — with prices, where/when it turns up, and its lines.</summary>
    public class ItemDef
    {
        public string id, name, model;
        public Kind kind;
        public ZoneMask zones;
        public int price;
        public float weight;          // relative spawn weight within its zones
        public ShadowSize shadow;
        public bool night, day = true, storm, rare, legendary;
        public string caught;          // "You caught a …!" quip
        public string lore;            // Professor Inkwell's museum line
        public Color tint = Color.white;

        public bool Sellable => kind == Kind.Fish || kind == Kind.Crab;
        public bool Donatable => kind != Kind.Junk;
    }

    public static class Catalog
    {
        public static readonly List<ItemDef> All = new List<ItemDef>();
        static readonly Dictionary<string, ItemDef> map = new Dictionary<string, ItemDef>();

        static ItemDef Add(ItemDef d)
        {
            if (d.model == null) d.model = (d.kind == Kind.Fish ? "fish/" : d.kind == Kind.Crab ? "crabs/" : d.kind == Kind.Treasure ? "treasure/" : "junk/") + d.id;
            All.Add(d);
            map[d.id] = d;
            return d;
        }

        public static ItemDef Get(string id) => id != null && map.TryGetValue(id, out var d) ? d : null;

        public static IEnumerable<ItemDef> OfKind(Kind k)
        {
            foreach (var d in All) if (d.kind == k) yield return d;
        }

        static Catalog()
        {
            const ZoneMask S = ZoneMask.Shallows, K = ZoneMask.Kelp, D = ZoneMask.Deep;
            // ---------------------------------------------------------------- fish
            Add(new ItemDef { id = "herring", name = "Herring", kind = Kind.Fish, zones = S | K, price = 12, weight = 10, shadow = ShadowSize.Small,
                caught = "A herring! Silver as Gran's teaspoons.", lore = "Herring travel in schools so big they once paid this harbour's wages. Every one of these little fellows was a coin to someone." });
            Add(new ItemDef { id = "smelt", name = "Smelt", kind = Kind.Fish, zones = S, price = 10, weight = 8, shadow = ShadowSize.Tiny,
                caught = "A smelt! It smells a bit like cucumber. Odd.", lore = "Fresh smelt really do smell of cucumber. Nobody knows why. I have written three letters to the fish about it." });
            Add(new ItemDef { id = "mackerel", name = "Mackerel", kind = Kind.Fish, zones = S | K, price = 18, weight = 8, shadow = ShadowSize.Small,
                caught = "A mackerel! Stripy, speedy and very pleased with itself.", lore = "Mackerel never stop swimming. Not once. I find that exhausting just to say." });
            Add(new ItemDef { id = "flounder", name = "Flounder", kind = Kind.Fish, zones = S, price = 30, weight = 5, shadow = ShadowSize.Medium,
                caught = "A flounder! Both eyes on one side, like it's sharing a secret.", lore = "A young flounder swims upright, then one eye wanders over the top of its head. Growing up is strange for everyone." });
            Add(new ItemDef { id = "cod", name = "Cod", kind = Kind.Fish, zones = S | K, price = 45, weight = 5, shadow = ShadowSize.Medium,
                caught = "A cod! It has a little chin whisker. Distinguished.", lore = "The cod's chin barbel tastes the seabed. Imagine licking the floor for a living, and being proud of it." });
            Add(new ItemDef { id = "salmon", name = "Salmon", kind = Kind.Fish, zones = K, price = 70, weight = 5, shadow = ShadowSize.Large,
                caught = "A salmon! It looks like it has somewhere very important to be.", lore = "Salmon remember the stream they hatched in and swim home years later. I can't remember where I put my monocle." });
            Add(new ItemDef { id = "rockfish", name = "Rockfish", kind = Kind.Fish, zones = K, price = 55, weight = 5, shadow = ShadowSize.Medium,
                caught = "A rockfish! Spiny, orange and grumpy about it.", lore = "Some rockfish live past two hundred years. This one may well be older than the harbour. Do be polite." });
            Add(new ItemDef { id = "lingcod", name = "Lingcod", kind = Kind.Fish, zones = K | D, price = 90, weight = 3, shadow = ShadowSize.Large,
                caught = "A lingcod! All mouth and mottles.", lore = "Neither a ling nor a cod, the lingcod is a greenling with an identity problem and an enormous appetite." });
            Add(new ItemDef { id = "halibut", name = "Halibut", kind = Kind.Fish, zones = K | D, price = 140, weight = 2, shadow = ShadowSize.Huge,
                caught = "A halibut! It's the size of a door. A whole door!", lore = "Halibut can grow bigger than a walrus. Walter insists this is not true. Walter has not met the large ones." });
            Add(new ItemDef { id = "wolf_eel", name = "Wolf Eel", kind = Kind.Fish, zones = K, price = 120, weight = 2, shadow = ShadowSize.Long,
                caught = "A wolf eel! Face only a mother could love. And I love it.", lore = "Wolf eels pair for life and share a cosy den. Under that frightful face beats a very domestic heart." });
            Add(new ItemDef { id = "sablefish", name = "Sablefish", kind = Kind.Fish, zones = D, price = 110, weight = 4, shadow = ShadowSize.Medium,
                caught = "A sablefish! Black velvet, buttery and fancy.", lore = "Also called black cod, though it is no cod. Chefs in faraway cities pay a fortune for its buttery flesh." });
            Add(new ItemDef { id = "lumpsucker", name = "Lumpsucker", kind = Kind.Fish, zones = D, price = 160, weight = 2, shadow = ShadowSize.Small,
                caught = "A lumpsucker! A tiny round bouncy ball of a fish! Oh, I could cry.", lore = "The lumpsucker clings to rocks with a sucker on its belly. A small, round, stubborn little marvel." });
            Add(new ItemDef { id = "ratfish", name = "Ratfish", kind = Kind.Fish, zones = D, price = 150, weight = 2, shadow = ShadowSize.Medium, night = true,
                caught = "A ratfish! Big green eyes like a ghost's lantern.", lore = "Ratfish are cousins of the sharks, older than the dinosaurs. Those great eyes glow green in the dark. Spooky and sweet." });
            Add(new ItemDef { id = "anglerfish", name = "Anglerfish", kind = Kind.Fish, zones = D, price = 260, weight = 1, shadow = ShadowSize.Large, night = true, rare = true,
                caught = "An anglerfish! It brought its own lamp. How thoughtful.", lore = "In the black deep, the anglerfish dangles a glowing lure. Every light down there is a promise, and not all promises are kind." });
            Add(new ItemDef { id = "sunfish", name = "Ocean Sunfish", kind = Kind.Fish, zones = K | D, price = 600, weight = 0.4f, shadow = ShadowSize.Huge, rare = true,
                caught = "An ocean sunfish! It's mostly face! A great, flat, puzzled face!", lore = "The mola basks at the surface to warm up after deep dives. It looks like a fish that forgot to finish being made. I adore it." });
            Add(new ItemDef { id = "oarfish", name = "Oarfish", kind = Kind.Fish, zones = D, price = 1200, weight = 0.15f, shadow = ShadowSize.Long, storm = true, legendary = true,
                caught = "THE OARFISH! The sea serpent of the old stories! Gran won't believe— well. Gran would believe it.", lore = "Sailors once took the oarfish for a sea serpent. It is said to rise only when the sea is angry. You have brought me a legend, Pip." });
            // ---------------------------------------------------------------- crabs (crab pots)
            Add(new ItemDef { id = "dungeness", name = "Dungeness Crab", kind = Kind.Crab, zones = S | K, price = 40, weight = 10,
                caught = "A Dungeness crab! Sweet as anything and twice as pinchy.", lore = "The Dungeness crab is the pride of every chowder pot from here to the cape. Handle with respect, and from behind." });
            Add(new ItemDef { id = "sea_urchin", name = "Sea Urchin", kind = Kind.Crab, zones = S | K | D, price = 25, weight = 5,
                caught = "A sea urchin! A pincushion that walks.", lore = "Urchins mow the kelp forests with five little teeth. A garden needs its gardeners, even spiky ones." });
            Add(new ItemDef { id = "snow_crab", name = "Snow Crab", kind = Kind.Crab, zones = K | D, price = 60, weight = 8,
                caught = "A snow crab! All legs, like a spider wearing stilts.", lore = "Snow crabs gather in their thousands on the cold seabed. Their long legs are the sweetest part, I'm told." });
            Add(new ItemDef { id = "red_king", name = "Red King Crab", kind = Kind.Crab, zones = D, price = 150, weight = 6,
                caught = "A red king crab! A real king! Bow, everyone!", lore = "The king crab of the cold north. Crews have braved the worst seas in the world for these spiny monarchs." });
            Add(new ItemDef { id = "golden_king", name = "Golden King Crab", kind = Kind.Crab, zones = D, price = 400, weight = 1, rare = true,
                caught = "A GOLDEN king crab! It practically glows!", lore = "Golden king crabs live deeper than their red cousins. A crew that hauls one is a crew with luck to spare." });
            // ---------------------------------------------------------------- treasures (dredge)
            Add(new ItemDef { id = "sea_glass", name = "Sea Glass", kind = Kind.Treasure, zones = S | K | D, price = 20, weight = 12,
                caught = "Sea glass! Frosted little jewels. Shelby will flip.", lore = "Broken bottles tumbled smooth by a hundred years of tide. The sea takes our litter and gives back jewels. Generous, really." });
            Add(new ItemDef { id = "message_bottle", name = "Message in a Bottle", kind = Kind.Treasure, zones = S | K, price = 60, weight = 6,
                caught = "A message in a bottle! Someone wrote to the sea, and the sea wrote back to me.", lore = "'To whoever finds this: I hope your nets are full and your boots are dry.' What a lovely thing to send into the world." });
            Add(new ItemDef { id = "brass_compass", name = "Brass Compass", kind = Kind.Treasure, zones = S | K, price = 90, weight = 5,
                caught = "A brass compass! The needle still points home.", lore = "A ship's compass, gimballed so it reads true however the deck rolls. It still points north. Some things simply know their way." });
            Add(new ItemDef { id = "pocket_watch", name = "Pocket Watch", kind = Kind.Treasure, zones = S | K, price = 110, weight = 4,
                caught = "A pocket watch! Stopped at ten past four. I wonder what happened then.", lore = "Stopped at ten past four, forever. Tea time, I suspect. A fine time to stop, if one must." });
            Add(new ItemDef { id = "ship_bell", name = "Ship's Bell", kind = Kind.Treasure, zones = K | D, price = 140, weight = 4,
                caught = "A ship's bell! Ding! Oh, it still rings!", lore = "Every ship's bell is cast with her name. This one says 'MARIGOLD, 1889'. She has come home to a harbour, at last." });
            Add(new ItemDef { id = "spyglass", name = "Spyglass", kind = Kind.Treasure, zones = K, price = 100, weight = 4,
                caught = "A spyglass! Now I can see… the inside of a spyglass. Needs a polish.", lore = "A brass telescope that once watched for storms and sweethearts. I'll give the lenses a good clean." });
            Add(new ItemDef { id = "ammonite", name = "Ammonite", kind = Kind.Treasure, zones = K | D, price = 120, weight = 4,
                caught = "An ammonite! A seashell older than old!", lore = "The ammonite swam these seas long before fish had faces worth mentioning. Its spiral is a perfect little clock of growth." });
            Add(new ItemDef { id = "pearl", name = "Giant Pearl", kind = Kind.Treasure, zones = K | D, price = 300, weight = 2, rare = true,
                caught = "A giant pearl! It's like holding the moon.", lore = "An oyster makes a pearl by wrapping an annoyance in beauty, layer upon layer. There's a lesson in that for all of us." });
            Add(new ItemDef { id = "gold_doubloon", name = "Gold Doubloons", kind = Kind.Treasure, zones = K | D, price = 250, weight = 2,
                caught = "Gold doubloons! Pirates! There were PIRATES!", lore = "Spanish gold, two centuries under the waves. How it reached our cold northern sea is a mystery I intend to enjoy for years." });
            Add(new ItemDef { id = "diving_helmet", name = "Diving Helmet", kind = Kind.Treasure, zones = K | D, price = 220, weight = 2,
                caught = "A diving helmet! Hello? Anyone in there? …No. Good.", lore = "Brass and glass, bolted to a canvas suit. The divers who wore these walked the seabed on lead boots. Brave, brave souls." });
            Add(new ItemDef { id = "megalodon_tooth", name = "Megalodon Tooth", kind = Kind.Treasure, zones = D, price = 260, weight = 2,
                caught = "A megalodon tooth! It's as big as my head! Bigger!", lore = "The tooth of a shark the size of a fishing boat. Gone for millions of years, thank goodness. Its smile must have been something." });
            Add(new ItemDef { id = "grand_conch", name = "Grand Conch", kind = Kind.Treasure, zones = K | D, price = 200, weight = 2,
                caught = "A grand conch! It's big enough to live in! Oh — Shelby!", lore = "Hold it to your ear and you'll hear the sea. Hold it to a hermit crab and you may hear 'MINE!'" });
            Add(new ItemDef { id = "figurehead", name = "Figurehead", kind = Kind.Treasure, zones = D, price = 350, weight = 1, rare = true,
                caught = "A figurehead! A carved mermaid, a bit chipped and very dignified.", lore = "Sailors believed the figurehead's eyes found the way through fog. She has the look of someone who has seen a great deal and forgiven most of it." });
            Add(new ItemDef { id = "porcelain_teapot", name = "Porcelain Teapot", kind = Kind.Treasure, zones = S | K, price = 130, weight = 3,
                caught = "A teapot! Not a single chip! Who drops a teapot in the ocean?", lore = "Blue willow pattern, not a crack on it. Somewhere, someone has been missing their tea for a hundred years. I shall make one in its honour." });
            Add(new ItemDef { id = "ship_lantern", name = "Ship's Lantern", kind = Kind.Treasure, zones = K | D, price = 160, weight = 3,
                caught = "A ship's lantern! Still has a bit of oil in it.", lore = "Red to port, green to starboard. This lantern kept a ship from harm on many a dark night. Let it rest in a lit room now." });
            Add(new ItemDef { id = "sextant", name = "Sextant", kind = Kind.Treasure, zones = D, price = 240, weight = 2,
                caught = "A sextant! For measuring stars. Or for looking clever.", lore = "With a sextant and the noon sun, a navigator could find her place on the whole round world. I still get lost in the museum." });
            Add(new ItemDef { id = "music_box", name = "Music Box", kind = Kind.Treasure, zones = K | D, price = 280, weight = 1, rare = true,
                caught = "A music box! It still plays… a little sea shanty!", lore = "It plays the old Saltmoss shanty. Your gran used to hum it on the pier, you know. Fancy that, after all these years." });
            Add(new ItemDef { id = "ship_in_bottle", name = "Ship in a Bottle", kind = Kind.Treasure, zones = S | K, price = 180, weight = 2,
                caught = "A ship in a bottle, in the sea, in my net! It's bottles all the way down!", lore = "Built with tweezers and patience on long voyages. A tiny ship that never sank, inside the sea that sank so many." });
            Add(new ItemDef { id = "sunken_crown", name = "Sunken Crown", kind = Kind.Treasure, zones = D, price = 800, weight = 0.4f, rare = true, legendary = true,
                caught = "A CROWN! A real crown! With seaweed on it! I'm a QUEEN of the SEA!", lore = "The lost crown of the Queen of the Grey Sea, from the old tale. I always said it was true. Well — I said it quietly." });
            Add(new ItemDef { id = "treasure_chest", name = "Treasure Chest", kind = Kind.Treasure, zones = D, price = 600, weight = 0.5f, rare = true,
                caught = "A TREASURE CHEST! Full of— well, full of sand mostly, but ALSO TREASURE!", lore = "Every child who ever played pirates dreamed of this exact moment, Pip. You've done it for all of them." });
            // ---------------------------------------------------------------- junk
            Add(new ItemDef { id = "old_boot", name = "Old Boot", kind = Kind.Junk, zones = S | K | D, price = 2, weight = 6,
                caught = "An old boot. A crab was living in it. Sorry, crab.", lore = "" });
            Add(new ItemDef { id = "tin_can", name = "Tin Can", kind = Kind.Junk, zones = S | K | D, price = 2, weight = 6,
                caught = "A tin can. 'Grandma Gull's Pickled Herring'. Tasty once, probably.", lore = "" });
            Add(new ItemDef { id = "tangled_net", name = "Tangled Net", kind = Kind.Junk, zones = S | K | D, price = 3, weight = 5,
                caught = "A tangled old net. Better in my hold than wrapped round a seal.", lore = "" });

            // shadow sizes for the pot catch are irrelevant; give fish defaults where unset
            foreach (var d in All) if (d.kind != Kind.Fish) d.shadow = ShadowSize.Medium;
        }

        public static ZoneMask MaskOf(Zone z) => z == Zone.Shallows ? ZoneMask.Shallows : z == Zone.Kelp ? ZoneMask.Kelp : ZoneMask.Deep;

        /// <summary>Weighted pick of a fish/crab/treasure for a zone and conditions.</summary>
        public static ItemDef Roll(Kind kind, Zone zone, bool night, float storm, System.Random rng, float luck = 0f)
        {
            float total = 0f;
            var pool = new List<(ItemDef d, float w)>();
            var zm = MaskOf(zone);
            foreach (var d in All)
            {
                if (d.kind != kind || (d.zones & zm) == 0) continue;
                if (d.night && !night) continue;
                if (d.storm && storm < 0.5f) continue;
                float w = d.weight * (d.rare ? 1f + luck : 1f) * (d.legendary ? 1f + luck * 2f : 1f);
                pool.Add((d, w));
                total += w;
            }
            if (pool.Count == 0) return null;
            double r = rng.NextDouble() * total;
            foreach (var p in pool)
            {
                r -= p.w;
                if (r <= 0) return p.d;
            }
            return pool[pool.Count - 1].d;
        }
    }
}
