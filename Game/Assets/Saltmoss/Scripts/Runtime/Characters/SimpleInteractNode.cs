namespace Saltmoss
{
    /// <summary>An interactable that plays a dialogue node (signs, boards, doors).</summary>
    public class SimpleInteractNode : Interactable
    {
        public string prompt = "Look";
        public string node;
        public string partner;
        public override string Prompt => prompt;
        public override bool CanInteract(PlayerController p) => !DialogueRunner.Active;
        public override void Interact(PlayerController p) => DialogueRunner.Play(node, partner);
    }
}
