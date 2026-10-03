using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Saltmoss
{
    /// <summary>
    /// The "stop-motion camera body" on the main camera: auto-focuses the depth of field on the subject (tabletop
    /// miniature look), adds the per-exposure lamp flicker of a real stage, and in full-film mode holds the camera pose
    /// between exposures.
    /// </summary>
    [DefaultExecutionOrder(9500)]
    public class ClayLens : MonoBehaviour
    {
        public Transform focusTarget;
        public float focusOffsetY = 0.6f;
        public float flicker = 0.025f;
        public bool depthOfField = true;
        public float apertureNear = 2.6f, apertureFar = 5.6f;

        Volume volume;
        DepthOfField dof;
        ColorAdjustments color;
        float baseExposure;
        float focus = 8f;
        Vector3 heldPos;
        Quaternion heldRot;
        bool held;

        void Start()
        {
            volume = FindAnyObjectByType<Volume>();
            if (volume != null && volume.profile != null)
            {
                volume.profile.TryGet(out dof);
                volume.profile.TryGet(out color);
                if (color != null) baseExposure = color.postExposure.value;
            }
        }

        public float FocusDistance => focus;

        void LateUpdate()
        {
            float target = focus;
            if (focusTarget != null)
            {
                var p = focusTarget.position + Vector3.up * focusOffsetY;
                target = Vector3.Dot(p - transform.position, transform.forward);
            }
            focus = Mathf.Lerp(focus, Mathf.Max(0.5f, target), 1f - Mathf.Exp(-Time.unscaledDeltaTime * 6f));
            if (dof != null)
            {
                dof.active = depthOfField && Settings.DepthOfField;
                dof.focusDistance.value = focus;
                // closer subjects: shallower focus, like a real macro lens on a tabletop set
                dof.aperture.value = Mathf.Lerp(apertureNear, apertureFar, Mathf.InverseLerp(3f, 30f, focus));
            }
            if (color != null && ClayClock.SteppedThisFrame && ClayClock.Fps > 0)
                color.postExposure.value = baseExposure + (Random.value - 0.5f) * 2f * flicker;

            if (ClayClock.FilmCamera)
            {
                if (!held || ClayClock.SteppedThisFrame)
                {
                    heldPos = transform.position;
                    heldRot = transform.rotation;
                    held = true;
                }
                transform.SetPositionAndRotation(heldPos, heldRot);
            }
            else held = false;
        }
    }
}
