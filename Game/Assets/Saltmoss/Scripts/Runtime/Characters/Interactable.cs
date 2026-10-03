using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Something Pip can walk up to and use: a person, a door, a counter, the boat.</summary>
    public abstract class Interactable : MonoBehaviour
    {
        public static readonly List<Interactable> All = new List<Interactable>();
        public float radius = 1.8f;
        public int priority;
        public Vector3 anchorOffset = new Vector3(0, 1.2f, 0);

        protected virtual void OnEnable() => All.Add(this);
        protected virtual void OnDisable() => All.Remove(this);

        public abstract string Prompt { get; }
        public virtual bool CanInteract(PlayerController p) => true;
        public abstract void Interact(PlayerController p);
        public Vector3 Anchor => transform.position + anchorOffset;

        public static Interactable Best(Vector3 pos, Vector3 forward, PlayerController p)
        {
            Interactable best = null;
            float bestScore = float.MaxValue;
            foreach (var i in All)
            {
                if (i == null || !i.isActiveAndEnabled) continue;
                var d = i.transform.position - pos;
                d.y *= 0.3f;
                float dist = d.magnitude;
                if (dist > i.radius || !i.CanInteract(p)) continue;
                float facing = Vector3.Dot(forward, d.normalized);
                float score = dist - facing * 0.8f - i.priority;
                if (score < bestScore) { bestScore = score; best = i; }
            }
            return best;
        }
    }
}
