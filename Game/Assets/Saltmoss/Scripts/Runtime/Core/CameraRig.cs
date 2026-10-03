using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Third-person camera for the tabletop set: follows the player (on foot or at the helm) with a long-ish lens from a
    /// little above, orbits with the right stick / right mouse button, eases back behind the direction of travel,
    /// pulls in when scenery is in the way, and can be overridden by dialogue and cinematic framings.
    /// Runs every frame (smooth); ClayLens holds it between exposures in full-film mode.
    /// </summary>
    [DefaultExecutionOrder(9000)]
    public class CameraRig : MonoBehaviour
    {
        public static CameraRig I { get; private set; }

        public Transform target;
        public float pivotHeight = 1.0f;
        public float distance = 7.5f, minDistance = 3.2f, maxDistance = 13f;
        public float yaw, pitch = 20f;
        public float minPitch = -5f, maxPitch = 65f;
        public bool boatMode;
        public LayerMask obstacles = 1 << 10;

        float autoYawHold;
        Vector3 pivot, vel;
        Vector3 camPos;
        Quaternion camRot = Quaternion.identity;
        float curDist;

        // override framing (dialogue / cinematic)
        bool hasOverride;
        Vector3 ovPos;
        Quaternion ovRot;
        float ovBlend;
        float ovFov = -1f;
        float baseFov;
        Camera cam;

        void Awake()
        {
            I = this;
            cam = GetComponent<Camera>();
            baseFov = cam != null ? cam.fieldOfView : 34f;
            camPos = transform.position;
            camRot = transform.rotation;
            curDist = distance;
        }

        public void SnapBehindTarget()
        {
            if (target == null) return;
            yaw = FreeYaw(target.eulerAngles.y);
            pivot = target.position + Vector3.up * pivotHeight;
            vel = Vector3.zero;
            curDist = distance;
            Compute(true);
            transform.SetPositionAndRotation(camPos, camRot);
        }

        /// <summary>The yaw nearest to `want` whose camera line isn't blocked by a wall (spawning by a door, etc.).</summary>
        float FreeYaw(float want)
        {
            var piv = target.position + Vector3.up * pivotHeight;
            float best = want, bestFree = -1f;
            for (int k = 0; k < 12; k++)
            {
                float y = want + (k % 2 == 0 ? 1 : -1) * ((k + 1) / 2) * 30f;
                var dir = Quaternion.Euler(pitch, y, 0f) * Vector3.back;
                float free = Physics.SphereCast(piv, 0.35f, dir, out var hit, distance, obstacles, QueryTriggerInteraction.Ignore) ? hit.distance : distance;
                if (free >= distance * 0.95f) return y;
                if (free > bestFree) { bestFree = free; best = y; }
            }
            return best;
        }

        public void SetOverride(Vector3 pos, Quaternion rot, float fov = -1f)
        {
            hasOverride = true;
            ovPos = pos;
            ovRot = rot;
            ovFov = fov;
        }

        public void ClearOverride() { hasOverride = false; ovFov = -1f; }

        public bool HasOverride => hasOverride;

        void LateUpdate()
        {
            if (target == null) return;
            Compute(false);
            ovBlend = Mathf.MoveTowards(ovBlend, hasOverride ? 1f : 0f, Time.unscaledDeltaTime * 2.2f);
            float b = Mathf.SmoothStep(0f, 1f, ovBlend);
            var p = Vector3.Lerp(camPos, ovPos, b);
            var r = Quaternion.Slerp(camRot, ovRot, b);
            transform.SetPositionAndRotation(p, r);
            if (cam != null)
            {
                float fov = boatMode ? baseFov + 4f : baseFov;
                cam.fieldOfView = Mathf.Lerp(fov, ovFov > 0 ? ovFov : fov, b);
            }
        }

        void Compute(bool snap)
        {
            float dt = Time.unscaledDeltaTime;
            bool input = Time.timeScale > 0f && !hasOverride;
            if (input)
            {
                var look = GameInput.LookDelta();
                if (look.sqrMagnitude > 0.0001f) autoYawHold = 2.5f;
                yaw += look.x;
                pitch = Mathf.Clamp(pitch - look.y, minPitch, maxPitch);
                float z = GameInput.ZoomDelta();
                if (Mathf.Abs(z) > 0.01f) distance = Mathf.Clamp(distance - Mathf.Sign(z) * 0.8f, minDistance, maxDistance);
                if (GameInput.Recenter.WasPressedThisFrame()) autoYawHold = 0f;
            }
            autoYawHold -= dt;

            // ease back behind the direction of travel
            var mover = target.GetComponent<IFollowHint>();
            if (mover != null && autoYawHold <= 0f && mover.FollowSpeed > 0.5f)
            {
                float want = mover.FollowYaw;
                float rate = boatMode ? 0.9f : 1.6f;
                yaw = Mathf.LerpAngle(yaw, want, 1f - Mathf.Exp(-dt * rate * Mathf.Clamp01(mover.FollowSpeed / 4f)));
            }

            var wantPivot = target.position + Vector3.up * pivotHeight;
            pivot = snap ? wantPivot : Vector3.SmoothDamp(pivot, wantPivot, ref vel, boatMode ? 0.25f : 0.12f, Mathf.Infinity, dt);
            float wantDist = distance;
            var rot = Quaternion.Euler(pitch, yaw, 0f);
            var dir = rot * Vector3.back;
            if (Physics.SphereCast(pivot, 0.35f, dir, out var hit, wantDist, obstacles, QueryTriggerInteraction.Ignore))
                wantDist = Mathf.Max(minDistance * 0.5f, hit.distance - 0.2f);
            curDist = snap ? wantDist : Mathf.Lerp(curDist, wantDist, 1f - Mathf.Exp(-dt * (wantDist < curDist ? 14f : 3f)));
            camPos = pivot + dir * curDist;
            // never dip below the sea surface
            float sea = SeaState.I != null ? SeaState.I.HeightAt(camPos.x, camPos.z) : 0f;
            if (camPos.y < sea + 0.6f) camPos.y = sea + 0.6f;
            camRot = Quaternion.LookRotation(pivot + Vector3.up * 0.15f - camPos);
        }
    }

    /// <summary>Implemented by things the camera follows: where they're heading and how fast.</summary>
    public interface IFollowHint
    {
        float FollowYaw { get; }
        float FollowSpeed { get; }
    }
}
