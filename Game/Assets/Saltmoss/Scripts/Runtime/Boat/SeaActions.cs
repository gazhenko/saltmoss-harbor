using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// What Pip can do from the deck right now, and the prompt that says so. Interact: haul a pot, lower the dredge,
    /// tie up at the berth, chip ice, drop a pot. Use tool: cast a line.
    /// </summary>
    public class SeaActions : MonoBehaviour
    {
        void Update()
        {
            var boat = BoatController.I;
            if (boat == null || !boat.Aboard || boat.Docked || boat.Busy || boat.JustBoarded || PlayerController.Locked) return;
            var pots = CrabPots.I;
            var dredge = Dredge.I;
            var ice = SeaHazards.I;
            var pos = boat.transform.position;
            float spd = Mathf.Abs(boat.Speed);

            string interact = null;
            System.Action act = null;
            var pot = pots != null ? pots.Nearest(pos, 9f) : null;
            if (pot != null && spd < 2.2f)
            {
                int n = CrabPots.Crabs(pot);
                interact = n == 0 ? "Haul pot (still soaking…)" : "Haul pot";
                act = () => pots.Haul(boat, pot);
            }
            else if (dredge != null && dredge.CanDredge(boat)) { interact = "Lower the dredge"; act = () => dredge.Lower(boat); }
            else if (boat.LeftBerth && Vector3.Distance(pos, boat.berthPos) < 12f && spd < 3f) { interact = "Tie up at the berth"; act = boat.TieUp; }
            else if (ice != null && ice.CanChip(boat)) { interact = "Knock off the ice"; act = () => ice.Chip(boat); }
            else if (pots != null && pots.CanDrop(boat)) { interact = $"Drop a crab pot ({CrabPots.OnDeck} aboard)"; act = () => pots.Drop(boat); }
            else if (pot != null) interact = "Slow down to haul";

            bool canCast = RodFishing.I != null && RodFishing.I.CanCast(boat) && !boat.InHarbour;
            if (interact != null)
            {
                HUD.ActionPrompt = interact;
                HUD.ActionKey = "Interact";
                if (act != null && GameInput.Interact.WasPressedThisFrame()) act();
            }
            else if (canCast)
            {
                HUD.ActionPrompt = "Cast a line";
                HUD.ActionKey = "UseTool";
            }
            if (canCast && GameInput.UseTool.WasPressedThisFrame()) RodFishing.I.Cast(boat);
        }
    }
}
