using System.Collections.Generic;

namespace Saltmoss
{
    public enum Weather { Clear, Breezy, Showers, Fog, Squalls, Storm }

    public class UpgradeDef
    {
        public string id, name, desc, requires;
        public int cost;
        public bool shop;   // sold by Nell (shop) vs Walter (boatyard)
    }

    public static class Upgrades
    {
        public static readonly List<UpgradeDef> All = new List<UpgradeDef>
        {
            // Walter's boatyard
            new UpgradeDef { id = "pots_1", name = "Third Crab Pot", cost = 260, desc = "One more pot on the deck. More pots, more crabs, more chowder." },
            new UpgradeDef { id = "pots_2", name = "Pot Stack (4)", cost = 700, requires = "pots_1", desc = "Four pots stacked and lashed. Real crabber's business." },
            new UpgradeDef { id = "pots_3", name = "Full Deck (6)", cost = 1600, requires = "pots_2", desc = "Six pots — the Sally Mae hasn't carried this many since your gran's best season." },
            new UpgradeDef { id = "hold_1", name = "Bigger Hold", cost = 380, desc = "Room for 24 in the hold instead of 14." },
            new UpgradeDef { id = "hold_2", name = "Ice Hold", cost = 1100, requires = "hold_1", desc = "A packed ice hold for 36. Keeps the catch happy." },
            new UpgradeDef { id = "winch", name = "Geared Winch", cost = 480, desc = "A stronger winch. The green zone on every haul is wider." },
            new UpgradeDef { id = "hull", name = "Doubled Hull Planks", cost = 900, desc = "The Sally Mae shrugs off rogue waves and sheds ice faster." },
            new UpgradeDef { id = "lights", name = "Deck Lights", cost = 340, desc = "Work the pots after dark. Night fish come up to see the lights." },
            new UpgradeDef { id = "sonar", name = "Old Sonar Set", cost = 650, desc = "Pings treasure on the screen and shows how deep to drop the dredge." },
            // Nell's shop improvements
            new UpgradeDef { id = "display", name = "Big Ice Display", cost = 420, shop = true, desc = "Twelve trays on the counter. More choice, more customers." },
            new UpgradeDef { id = "ice", name = "Crushed Ice", cost = 300, shop = true, desc = "Everything looks fresher on crushed ice. +15% on every sale." },
            new UpgradeDef { id = "lanterns", name = "Pier Lanterns", cost = 360, shop = true, desc = "Light up the pier so folk shop in the evening." },
            new UpgradeDef { id = "paint", name = "Fresh Paint & Sign", cost = 760, shop = true, requires = "lanterns", desc = "A proper sign and a coat of paint. The Salty Puffin, open for business!" },
            new UpgradeDef { id = "bunting", name = "Bunting", cost = 220, shop = true, desc = "Little flags all along the pier. Pure joy, no practical use." },
        };

        public static UpgradeDef Get(string id) => All.Find(u => u.id == id);

        public static bool Available(UpgradeDef u) =>
            !GameState.Has(u.id) && (string.IsNullOrEmpty(u.requires) || GameState.Has(u.requires));
    }
}
