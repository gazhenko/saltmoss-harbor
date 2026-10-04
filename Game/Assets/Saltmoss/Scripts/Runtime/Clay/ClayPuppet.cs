using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Put on the visual child of anything that moves (characters, boats, gulls, buoys, pots). Gameplay moves the
    /// parent every frame; the puppet only takes up the parent's pose when the stop-motion clock exposes a new frame
    /// and holds it in between, so the motion reads as hand-animated on twos.
    /// The one exception is whatever the camera is following (and anything riding on it): the camera glides every
    /// frame, so holding that puppet's travel would make it slide back and jump forward against the camera. It
    /// travels with its parent and only its own pose (bob, lean, pitch and roll from the offsets) keeps to the steps.
    /// </summary>
    [DefaultExecutionOrder(9000)]
    public class ClayPuppet : MonoBehaviour
    {
        Vector3 restLocalPos;
        Quaternion restLocalRot;
        Vector3 heldPos, heldLocalPos;
        Quaternion heldRot, heldLocalRot;
        bool has;
        /// <summary>Optional extra per-step offset (local to the parent), e.g. a bob or lean from an animator.</summary>
        public Vector3 offsetPos;
        public Quaternion offsetRot = Quaternion.identity;

        void Awake()
        {
            restLocalPos = transform.localPosition;
            restLocalRot = transform.localRotation;
        }

        void OnEnable() => has = false;

        /// <summary>Take the parent's pose right now (after teleports, cut-scene cuts).</summary>
        public void Snap()
        {
            has = false;
            Apply();
            appliedFrame = -1;   // the parent may still move this frame: pose again in LateUpdate
        }

        int appliedFrame = -1;
        Transform ancestorFor;
        ClayPuppet ancestor;

        void LateUpdate() => Apply();

        void Apply()
        {
            if (appliedFrame == Time.frameCount && has) return;
            appliedFrame = Time.frameCount;
            var p = transform.parent;
            if (p == null) return;
            // a puppet riding inside another (Pip in the boat) reads its carrier's pose this frame, so pose that first
            if (ancestorFor != p) { ancestorFor = p; ancestor = p.GetComponentInParent<ClayPuppet>(); }
            if (ancestor != null) ancestor.Apply();
            if (!has || ClayClock.SteppedThisFrame)
            {
                heldLocalPos = restLocalPos + offsetPos;
                heldLocalRot = offsetRot * restLocalRot;
                heldPos = p.TransformPoint(heldLocalPos);
                heldRot = p.rotation * heldLocalRot;
                has = true;
            }
            // the followed thing and everything riding on it (Pip at the helm, pots and catch on deck)
            var target = CameraRig.I != null ? CameraRig.I.target : null;
            bool followed = target != null && p.IsChildOf(target);
            if (followed) transform.SetPositionAndRotation(p.TransformPoint(heldLocalPos), p.rotation * heldLocalRot);
            else transform.SetPositionAndRotation(heldPos, heldRot);
        }
    }
}
