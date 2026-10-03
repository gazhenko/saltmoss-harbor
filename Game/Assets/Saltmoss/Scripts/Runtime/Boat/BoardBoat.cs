namespace Saltmoss
{
    /// <summary>Step aboard the Sally Mae from the floating dock.</summary>
    public class BoardBoat : Interactable
    {
        public override string Prompt => GameState.Flag("met_walter") ? "Board the Sally Mae" : "Board the Sally Mae (ask Walter first)";
        public override bool CanInteract(PlayerController p) => BoatController.I != null && BoatController.I.Docked && !p.Aboard;

        public override void Interact(PlayerController p)
        {
            if (!GameState.Flag("met_walter")) { DialogueRunner.Play("boat_locked", "pip"); return; }
            if (GameState.D.hour >= 22.5f) { DialogueRunner.Play("boat_late", "pip"); return; }
            BoatController.I.Board();
        }
    }
}
