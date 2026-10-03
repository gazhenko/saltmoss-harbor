using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// A townsfolk puppet at their post: turns to watch Pip come near, mumbles a hello, fidgets with little gestures,
    /// optionally potters about a small area (Shelby), and opens their dialogue hub ("&lt;id&gt;_hub") when spoken to.
    /// </summary>
    public class Npc : Interactable
    {
        public string id;
        public string hub;
        public CritterAnimator anim;
        public FaceRig face;
        public Transform visual;
        public float wanderRadius;
        public Vector3 home;
        public float homeYaw;

        float greetCooldown, fidget = 4f, wanderTimer = 3f;
        Vector3 wanderTarget;
        bool near;

        public override string Prompt => "Talk to " + Cast.Get(id).name;

        void Start()
        {
            home = transform.position;
            homeYaw = transform.eulerAngles.y;
            wanderTarget = home;
            if (string.IsNullOrEmpty(hub)) hub = id + "_hub";
            DialogueRunner.Register(id, transform, face, anim);
            VoiceBlips.I?.Warm(Cast.Get(id).voice);
        }

        public override bool CanInteract(PlayerController p) => !DialogueRunner.Active && isActiveAndEnabled;

        public override void Interact(PlayerController p)
        {
            AudioDirector.UI("ui_open", 0.3f);
            DialogueRunner.Play(hub, id, () => greetCooldown = 20f);
        }

        void Update()
        {
            var p = PlayerController.I;
            float dt = Time.deltaTime;
            greetCooldown -= dt;
            if (p == null || DialogueRunner.Active) { if (anim) anim.speed = 0f; return; }
            var to = p.transform.position - transform.position;
            to.y = 0f;
            float dist = to.magnitude;
            bool nowNear = dist < 6f;
            if (nowNear && !near && greetCooldown <= 0f && !p.Aboard)
            {
                VoiceBlips.I?.Mumble(Cast.Get(id).voice);
                face?.Bounce();
                if (anim && Random.value < 0.5f) anim.Play(Gesture.Wave, 1.2f);
                greetCooldown = 45f;
            }
            near = nowNear;
            if (face) face.lookTarget = nowNear ? p.transform : null;

            float speed = 0f;
            if (nowNear)
            {
                var want = Quaternion.LookRotation(to.sqrMagnitude > 0.01f ? to : transform.forward);
                transform.rotation = Quaternion.RotateTowards(transform.rotation, want, 160f * dt);
            }
            else if (wanderRadius > 0f)
            {
                wanderTimer -= dt;
                var d = wanderTarget - transform.position;
                d.y = 0f;
                if (d.magnitude > 0.2f)
                {
                    speed = 0.9f;
                    transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(d), 200f * dt);
                    transform.position += transform.forward * speed * dt;
                }
                else if (wanderTimer <= 0f)
                {
                    var r = Random.insideUnitCircle * wanderRadius;
                    wanderTarget = home + new Vector3(r.x, 0f, r.y);
                    wanderTimer = Random.Range(3f, 7f);
                }
                // stick to the ground
                if (Physics.Raycast(transform.position + Vector3.up * 1.5f, Vector3.down, out var hit, 4f, 1 << 10))
                    transform.position = new Vector3(transform.position.x, hit.point.y, transform.position.z);
            }
            else
            {
                transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.Euler(0f, homeYaw, 0f), 60f * dt);
            }
            if (anim) anim.speed = speed;

            fidget -= dt;
            if (fidget <= 0f && anim != null && !anim.Busy)
            {
                fidget = Random.Range(6f, 14f);
                var g = Random.value;
                anim.Play(g < 0.3f ? Gesture.Nod : g < 0.5f ? Gesture.Think : g < 0.65f ? Gesture.Shrug : Gesture.None, 1.4f);
            }
        }
    }
}
