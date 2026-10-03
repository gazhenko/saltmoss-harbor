using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Put on the visual child of anything that moves (characters, boats, gulls, buoys, pots). Gameplay moves the
    /// parent every frame; the puppet only takes up the parent's pose when the stop-motion clock exposes a new frame
    /// and holds it in between, so the motion reads as hand-animated on twos.
    /// </summary>
    [DefaultExecutionOrder(9000)]
    public class ClayPuppet : MonoBehaviour
    {
        Vector3 restLocalPos;
        Quaternion restLocalRot;
        Vector3 heldPos;
        Quaternion heldRot;
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
            LateUpdate();
        }

        void LateUpdate()
        {
            var p = transform.parent;
            if (p == null) return;
            if (!has || ClayClock.SteppedThisFrame)
            {
                heldPos = p.TransformPoint(restLocalPos + offsetPos);
                heldRot = p.rotation * (offsetRot * restLocalRot);
                has = true;
            }
            transform.SetPositionAndRotation(heldPos, heldRot);
        }
    }
}
