using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Pip on foot: camera-relative walking and running on the boardwalks, beach and decks, interaction with whatever
    /// is in front, and handing control to the boat at the helm. The visual puppet steps on twos; this logic doesn't.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour, IFollowHint
    {
        public static PlayerController I { get; private set; }

        public float walkSpeed = 2.4f, runSpeed = 4.3f, turnRate = 720f, gravity = 22f;
        public CritterAnimator anim;
        public FaceRig face;
        public ClayModel model;
        public Transform visual;

        CharacterController cc;
        Vector3 velocity;
        float vy;
        float stepAccum;
        public Interactable Focus { get; private set; }
        public bool Aboard { get; private set; }
        public float Speed { get; private set; }

        /// <summary>Anything that should freeze Pip (dialogue, menus, cut-scenes) sets this.</summary>
        public static int LockCount;
        public static bool Locked => LockCount > 0;

        public float FollowYaw => transform.eulerAngles.y;
        public float FollowSpeed => Aboard ? 0f : Speed;

        void Awake()
        {
            I = this;
            cc = GetComponent<CharacterController>();
        }

        public void Teleport(Vector3 pos, float yaw)
        {
            cc.enabled = false;
            transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
            cc.enabled = !Aboard;
            vy = 0f;
            velocity = Vector3.zero;
            visual?.GetComponent<ClayPuppet>()?.Snap();
        }

        /// <summary>Stand Pip on the boat (parented, no controller) at a deck socket.</summary>
        public void Board(Transform spot, Activity act)
        {
            Aboard = true;
            cc.enabled = false;
            transform.SetParent(spot, false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            anim.activity = act;
            anim.speed = 0f;
            Speed = 0f;
            visual?.GetComponent<ClayPuppet>()?.Snap();
        }

        public void MoveAboard(Transform spot, Activity act)
        {
            transform.SetParent(spot, false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            anim.activity = act;
        }

        public void Disembark(Vector3 pos, float yaw)
        {
            Aboard = false;
            transform.SetParent(null, true);
            anim.activity = Activity.None;
            Teleport(pos, yaw);
        }

        void Update()
        {
            if (Aboard) { Focus = null; return; }
            Vector2 mv = Locked ? Vector2.zero : GameInput.MoveVector;
            var cam = Camera.main != null ? Camera.main.transform : transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up).normalized;
            var right = Vector3.Cross(Vector3.up, fwd);
            var wish = fwd * mv.y + right * mv.x;
            bool run = !Locked && GameInput.Run.IsPressed();
            float target = wish.magnitude * (run ? runSpeed : walkSpeed);
            var wantVel = wish.sqrMagnitude > 0.001f ? wish.normalized * target : Vector3.zero;
            velocity = Vector3.MoveTowards(velocity, wantVel, (wantVel.sqrMagnitude > velocity.sqrMagnitude ? 14f : 18f) * Time.deltaTime);
            if (wish.sqrMagnitude > 0.01f)
            {
                var want = Quaternion.LookRotation(wish);
                transform.rotation = Quaternion.RotateTowards(transform.rotation, want, turnRate * Time.deltaTime);
            }
            if (cc.isGrounded) vy = -2f;
            else vy -= gravity * Time.deltaTime;
            cc.Move((velocity + Vector3.up * vy) * Time.deltaTime);
            var flat = cc.velocity;
            flat.y = 0f;
            Speed = flat.magnitude;
            // never fall into the sea: back onto the last solid ground
            if (transform.position.y < -1.5f) Teleport(lastGround, transform.eulerAngles.y);
            if (cc.isGrounded) lastGround = transform.position;

            if (anim != null)
            {
                anim.speed = Speed;
                anim.stride = 0.42f;
            }
            Footsteps();

            Focus = Locked ? null : Interactable.Best(transform.position, transform.forward, this);
            if (!Locked && Focus != null && GameInput.Interact.WasPressedThisFrame())
                Focus.Interact(this);
        }

        Vector3 lastGround;

        void Footsteps()
        {
            if (Speed < 0.3f || !cc.isGrounded) { stepAccum = 0f; return; }
            stepAccum += Speed * Time.deltaTime;
            if (stepAccum < 0.42f) return;
            stepAccum = 0f;
            string surface = "wood";
            if (Physics.Raycast(transform.position + Vector3.up * 0.3f, Vector3.down, out var hit, 1f, ~0, QueryTriggerInteraction.Ignore))
            {
                var n = hit.collider.name.ToLowerInvariant();
                if (n.Contains("tile") || n.Contains("terrain")) surface = hit.point.y < 2.2f ? "sand" : "stone";
            }
            AudioDirector.Footstep(surface, transform.position);
        }
    }
}
