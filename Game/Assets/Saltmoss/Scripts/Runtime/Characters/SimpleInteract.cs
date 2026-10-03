using UnityEngine;

namespace Saltmoss
{
    /// <summary>An interactable that just calls an action (doors, boards, signs).</summary>
    public class SimpleInteract : Interactable
    {
        public string prompt = "Look";
        public System.Action<PlayerController> onUse;
        public System.Func<PlayerController, bool> when;
        public override string Prompt => prompt;
        public override bool CanInteract(PlayerController p) => when == null || when(p);
        public override void Interact(PlayerController p) => onUse?.Invoke(p);
    }
}
