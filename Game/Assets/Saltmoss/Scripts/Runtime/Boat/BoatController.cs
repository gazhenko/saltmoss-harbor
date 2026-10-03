using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The Sally Mae: arcade helm handling (throttle, rudder, a run-on throttle), heave/pitch/roll from the clay sea on
    /// twos, wake foam, engine sound and smoke puffs, bumping off rocks and piers, the fog bank at the edge of the
    /// world, ice weight, rogue-wave sputters, and boarding / tying up at the berth.
    /// </summary>
    public class BoatController : MonoBehaviour, IFollowHint
    {
        public static BoatController I { get; private set; }

        public ClayModel model;
        public ClayPuppet puppet;
        public Transform helm, rail, winch, boomTip, smoke, stern, bow;
        public Transform[] potSlots = new Transform[0];
        public Vector3 berthPos;
        public float berthYaw;
        public Vector3 boardPoint;
        public float boardYaw;
        public float maxSpeed = 8.5f, boostSpeed = 11.5f, reverseSpeed = 2.6f;
        public float worldRadius = 780f;
        public Vector2 harbourMouth = new Vector2(0f, 75f);

        public bool Aboard { get; private set; }
        public bool Docked { get; private set; } = true;
        public float Speed { get; private set; }
        public float Ice;              // 0..1 ice on deck
        public float Sputter;          // seconds of engine trouble left
        public bool Busy;              // a minigame is running: no helm input
        /// <summary>Has she been out past the berth since Pip came aboard? (Only then is "tie up" on offer.)</summary>
        public bool LeftBerth { get; private set; }
        /// <summary>True on the frame Pip steps aboard, so the same key press can't also fire a deck action.</summary>
        public bool JustBoarded => boardedFrame == Time.frameCount;
        int boardedFrame = -1;
        /// <summary>Trailer/cut-scene autopilot: hold this speed and turn rate, ignore the helm.</summary>
        public bool autopilot;
        public float autoSpeed, autoTurn;
        public Zone CurrentZone { get; private set; } = Zone.Shallows;

        float throttle, rudder, yawRate;
        AudioSource engine;
        float smokeTimer, foamTimer;
        float heave, pitch, roll;
        Zone lastZone = (Zone)(-1);

        public float FollowYaw => transform.eulerAngles.y;
        public float FollowSpeed => Aboard ? Mathf.Abs(Speed) : 0f;

        void Awake()
        {
            I = this;
            engine = gameObject.AddComponent<AudioSource>();
            engine.loop = true;
            engine.spatialBlend = 0.6f;
            engine.minDistance = 6f;
            engine.maxDistance = 60f;
            engine.playOnAwake = false;
        }

        void Start()
        {
            var clip = AudioDirector.Bank != null ? AudioDirector.Bank.Get("engine_idle") : null;
            if (clip != null) { engine.clip = clip; engine.volume = 0f; engine.Play(); }
        }

        public Zone ZoneAt(Vector3 p)
        {
            float d = Vector2.Distance(new Vector2(p.x, p.z), harbourMouth);
            return d < 160f ? Zone.Shallows : d < 380f ? Zone.Kelp : Zone.Deep;
        }

        // the crests of the two harbour arms, west to east across the mouth (WEST_ARM/EAST_ARM in
        // Tools/clay/models/town_terrain.py); the basin is the water south of this line
        static readonly Vector2[] Arms =
        {
            new Vector2(-50f, 22f), new Vector2(-46f, 32f), new Vector2(-39f, 43f), new Vector2(-31f, 54f), new Vector2(-22f, 64f),
            new Vector2(-14f, 72f), new Vector2(-11.5f, 76f), new Vector2(12f, 76f), new Vector2(15.5f, 73f), new Vector2(24f, 69f),
            new Vector2(34f, 64f), new Vector2(45f, 59f), new Vector2(55f, 53f), new Vector2(63f, 46f),
        };

        /// <summary>Inside the harbour arms (the berth and the town piers), where pots and lines aren't allowed.</summary>
        public bool InHarbour => IsInHarbour(transform.position);

        public static bool IsInHarbour(Vector3 p)
        {
            if (p.x < Arms[0].x || p.x > Arms[Arms.Length - 1].x) return false;
            for (int i = 1; i < Arms.Length; i++)
                if (p.x <= Arms[i].x)
                    return p.z < Mathf.Lerp(Arms[i - 1].y, Arms[i].y, Mathf.InverseLerp(Arms[i - 1].x, Arms[i].x, p.x));
            return false;
        }

        public void Board()
        {
            var p = PlayerController.I;
            if (p == null) return;
            Aboard = true;
            Docked = false;
            LeftBerth = false;
            boardedFrame = Time.frameCount;
            p.Board(helm != null ? helm : transform, Activity.Helm);
            if (CameraRig.I != null)
            {
                CameraRig.I.target = transform;
                CameraRig.I.boatMode = true;
                CameraRig.I.distance = 15f;
                CameraRig.I.pivotHeight = 2.2f;
                CameraRig.I.maxDistance = 26f;
                CameraRig.I.pitch = 16f;
            }
            AudioDirector.Play("boat_horn", transform.position, 0.8f, 0f);
            Debug.Log("[Boat] Pip is aboard");
            if (GameFlow.I != null) GameFlow.I.place = GameFlow.Place.Sea;
            GameState.D.boatDocked = false;
        }

        public void TieUp()
        {
            Busy = true;
            StartCoroutine(TieUpCo());
        }

        System.Collections.IEnumerator TieUpCo()
        {
            Vector3 p0 = transform.position;
            float y0 = transform.eulerAngles.y;
            for (float t = 0; t < 1f; t += Time.deltaTime / 2.2f)
            {
                float e = Mathf.SmoothStep(0f, 1f, t);
                transform.position = Vector3.Lerp(p0, berthPos, e);
                transform.rotation = Quaternion.Euler(0f, Mathf.LerpAngle(y0, berthYaw, e), 0f);
                Speed = 0f;
                yield return null;
            }
            transform.SetPositionAndRotation(berthPos, Quaternion.Euler(0f, berthYaw, 0f));
            Docked = true;
            Aboard = false;
            Busy = false;
            GameState.D.boatDocked = true;
            Debug.Log("[Boat] tied up at the berth");
            var pl = PlayerController.I;
            pl.Disembark(boardPoint, boardYaw);
            if (CameraRig.I != null)
            {
                CameraRig.I.target = pl.transform;
                CameraRig.I.boatMode = false;
                CameraRig.I.distance = 7.5f;
                CameraRig.I.pivotHeight = 1.0f;
                CameraRig.I.maxDistance = 13f;
                CameraRig.I.SnapBehindTarget();
            }
            if (GameFlow.I != null) GameFlow.I.place = GameFlow.Place.Town;
            Unload();
        }

        /// <summary>Overnight tow (or a loaded save): the boat is back at its berth with nobody aboard.</summary>
        public void ForceDock()
        {
            StopAllCoroutines();
            transform.SetPositionAndRotation(berthPos, Quaternion.Euler(0f, berthYaw, 0f));
            Speed = 0f;
            Docked = true;
            Aboard = false;
            Busy = false;
            Ice = 0f;
            Sputter = 0f;
            GameState.D.boatDocked = true;
        }

        /// <summary>The crane swings the hold up into the Salty Puffin's cold store.</summary>
        public static void Unload()
        {
            var D = GameState.D;
            int n = GameState.Count(D.hold);
            if (n == 0) return;
            foreach (var s in D.hold) GameState.Add(D.stock, s.id, s.count, s.day);
            D.hold.Clear();
            GameState.Notify();
            AudioDirector.Play("chain_rattle", I != null ? I.transform.position : Vector3.zero, 0.7f);
            GameState.Say($"Unloaded {n} into the Salty Puffin's cold store.");
            GameState.SetFlag("unloaded_once");
        }

        void Update()
        {
            float dt = Time.deltaTime;
            if (autopilot)
            {
                Docked = false;
                Speed = Mathf.MoveTowards(Speed, autoSpeed, dt * 3f);
                throttle = Mathf.Clamp(autoSpeed / maxSpeed, -1f, 1f);
                transform.Rotate(0f, autoTurn * dt, 0f, Space.World);
                transform.position += transform.forward * Speed * dt;
                Waves();
                Effects(dt);
                return;
            }
            bool control = Aboard && !Busy && !PlayerController.Locked && !Docked;
            Vector2 mv = control ? GameInput.MoveVector : Vector2.zero;
            bool boost = control && GameInput.Run.IsPressed();
            Sputter = Mathf.Max(0f, Sputter - dt);
            float wantThrottle = mv.y;
            if (Sputter > 0f) wantThrottle *= 0.15f + 0.15f * Mathf.PerlinNoise(Time.time * 3f, 0f);
            throttle = Mathf.MoveTowards(throttle, wantThrottle, dt * 1.6f);
            rudder = Mathf.MoveTowards(rudder, mv.x, dt * 2.5f);

            float top = (boost ? boostSpeed : maxSpeed) * (1f - Ice * 0.45f);
            float target = throttle >= 0f ? throttle * top : throttle * reverseSpeed;
            float accel = target > Speed ? 1.6f : 2.4f;
            Speed = Mathf.MoveTowards(Speed, target, accel * dt);
            if (!Aboard && !Docked) Speed = Mathf.MoveTowards(Speed, 0f, dt);

            float steerEff = Mathf.Clamp01(Mathf.Abs(Speed) / 3f) * 0.85f + 0.15f;
            float wantYaw = rudder * 34f * steerEff * Mathf.Sign(Speed >= -0.1f ? 1f : -1f);
            yawRate = Mathf.Lerp(yawRate, wantYaw, 1f - Mathf.Exp(-dt * 2.5f));
            if (!Docked) transform.Rotate(0f, yawRate * dt, 0f, Space.World);

            if (!Docked && Mathf.Abs(Speed) > 0.01f)
            {
                var step = transform.forward * Speed * dt;
                // bump off rocks, piers and the shore
                if (Physics.SphereCast(transform.position + Vector3.up * 0.6f, 1.6f, step.normalized * Mathf.Sign(Speed), out var hit, Mathf.Abs(Speed) * dt + 2.4f, 1 << 10, QueryTriggerInteraction.Ignore))
                {
                    if (Mathf.Abs(Speed) > 2f) { AudioDirector.Play("hull_creak", transform.position, 0.9f); AudioDirector.Play("wave_slap", transform.position, 0.8f); GameInput.Impulse(0.4f, 0.6f, 0.3f); }
                    Speed = -Speed * 0.25f;
                    step = Vector3.zero;
                }
                transform.position += step;
            }
            // fog bank at the edge of the world
            var flat = new Vector2(transform.position.x, transform.position.z) - harbourMouth;
            if (flat.magnitude > worldRadius && Vector2.Dot(flat, new Vector2(transform.forward.x, transform.forward.z)) > 0f)
            {
                Speed *= 0.95f;
                transform.Rotate(0f, 40f * dt, 0f, Space.World);
                if (Random.value < dt * 0.4f) GameState.Say("The fog's too thick out here. Turn her around!");
            }
            var pos = transform.position;
            pos.y = 0f;
            transform.position = pos;
            if (Aboard && !LeftBerth && Vector3.Distance(pos, berthPos) > 16f) LeftBerth = true;

            Waves();
            Effects(dt);
            ZoneBanner();
        }

        void Waves()
        {
            if (!ClayClock.SteppedThisFrame || SeaState.I == null || puppet == null) return;
            var s = SeaState.I;
            Vector3 p = transform.position, f = transform.forward * 4.2f, r = transform.right * 1.5f;
            float hb = s.HeightAt(p.x + f.x, p.z + f.z), hs = s.HeightAt(p.x - f.x, p.z - f.z);
            float hp = s.HeightAt(p.x - r.x, p.z - r.z), hst = s.HeightAt(p.x + r.x, p.z + r.z);
            float wantHeave = (hb + hs + hp + hst) * 0.25f;
            float wantPitch = Mathf.Atan2(hs - hb, 8.4f) * Mathf.Rad2Deg;
            float wantRoll = Mathf.Atan2(hp - hst, 3f) * Mathf.Rad2Deg * 0.8f + rudder * Mathf.Clamp01(Speed / maxSpeed) * -4f;
            // the hull is heavy: it follows the swell with some lag
            heave = Mathf.Lerp(heave, wantHeave, 0.55f);
            pitch = Mathf.Lerp(pitch, wantPitch - Speed * 0.25f, 0.45f);
            roll = Mathf.Lerp(roll, wantRoll, 0.4f);
            puppet.offsetPos = new Vector3(0f, heave, 0f);
            puppet.offsetRot = Quaternion.Euler(pitch, 0f, roll);
        }

        void Effects(float dt)
        {
            float load = Mathf.Abs(throttle);
            if (engine.clip != null)
            {
                var run = AudioDirector.Bank.Get("engine_run");
                engine.volume = Mathf.Lerp(engine.volume, (Aboard || !Docked ? 0.35f + load * 0.35f : 0.12f) * Settings.Sfx, dt * 2f);
                engine.pitch = 0.85f + load * 0.45f + (Sputter > 0f ? Mathf.PerlinNoise(Time.time * 6f, 1f) * 0.3f : 0f);
            }
            foamTimer -= dt;
            if (Mathf.Abs(Speed) > 0.8f && foamTimer <= 0f)
            {
                foamTimer = 0.05f;
                float k = Mathf.Clamp01(Mathf.Abs(Speed) / maxSpeed);
                var back = stern != null ? stern.position : transform.position - transform.forward * 4.5f;
                var front = bow != null ? bow.position : transform.position + transform.forward * 4.5f;
                SeaState.AddFoam(back - transform.forward * 0.8f, 1.3f + k * 0.4f, 0.75f);
                SeaState.AddFoam(back - transform.forward * 4f + transform.right * 0.9f, 0.9f + k * 0.6f, 0.55f * k);
                SeaState.AddFoam(back - transform.forward * 4f - transform.right * 0.9f, 0.9f + k * 0.6f, 0.55f * k);
                SeaState.AddFoam(back - transform.forward * 9f + transform.right * 1.8f, 0.8f + k * 0.8f, 0.35f * k);
                SeaState.AddFoam(back - transform.forward * 9f - transform.right * 1.8f, 0.8f + k * 0.8f, 0.35f * k);
                SeaState.AddFoam(front + transform.right * 1.3f, 0.6f, 0.6f * k);
                SeaState.AddFoam(front - transform.right * 1.3f, 0.6f, 0.6f * k);
            }
            smokeTimer -= dt;
            if (smoke != null && smokeTimer <= 0f && (Aboard || !Docked))
            {
                smokeTimer = Mathf.Lerp(1.2f, 0.45f, load) * (Sputter > 0f ? 0.3f : 1f);
                CottonPuff.Emit(smoke.position, Sputter > 0f ? new Color(0.35f, 0.33f, 0.32f) : new Color(0.86f, 0.84f, 0.8f), 0.22f + load * 0.12f);
            }
            if (Aboard && GameInput.Horn.WasPressedThisFrame()) AudioDirector.Play("boat_horn", transform.position, 0.9f, 0f);
        }

        void ZoneBanner()
        {
            if (!Aboard) { lastZone = (Zone)(-1); return; }
            var z = ZoneAt(transform.position);
            CurrentZone = z;
            if (z == lastZone) return;
            if (lastZone >= 0 || z != Zone.Shallows)
            {
                string title = z == Zone.Shallows ? "THE SHALLOWS" : z == Zone.Kelp ? "KELP REACH" : "THE GREY DEEP";
                string sub = z == Zone.Shallows ? "calm water · herring, cod & dungeness" : z == Zone.Kelp ? "kelp forests · salmon, halibut & snow crab" : "big swell · king crab, legends & treasure";
                HUD.I?.Banner(title, sub);
                AudioDirector.UI("glimmer", 0.6f);
            }
            lastZone = z;
        }
    }
}
