using UnityEngine;

namespace Saltmoss
{
    public enum Gesture { None, Wave, Hop, Shrug, Nod, Shake, Think, Cheer, Droop, Point, Bow }
    public enum Activity { None, Cast, Reel, Haul, Hammer, Carry, Helm, Serve, Sleep, Sit, Crank }

    /// <summary>
    /// Procedural stop-motion performance for the critter rig (Docs/DESIGN.md §5.3): idle breathing and weight shifts,
    /// a walk/run cycle driven by distance travelled, talk gestures, emotes and work activities. The pose is computed
    /// only on stop-motion steps (and held between them), with a little per-step jitter like a hand-posed puppet.
    /// Missing bones are skipped, so the same animator drives puffins, walruses, otters, pelicans, gulls, seals,
    /// crabs and an octopus.
    /// </summary>
    [DefaultExecutionOrder(7000)]
    public class CritterAnimator : MonoBehaviour
    {
        public ClayModel model;
        /// <summary>Movement speed in m/s (set by the controller each frame).</summary>
        public float speed;
        public float stride = 0.55f;
        public bool grounded = true;
        public bool talking;
        public Activity activity;
        public float activityPhase;      // 0..1 driven by gameplay for scripted actions (cast swing, haul pull)
        public float personality = 1f;   // gesture amplitude
        public float sway = 1f;          // idle sway amount

        Gesture gesture;
        float gestureT, gestureLen;
        float walkPhase, idleT, talkT;
        float jitterSeed;
        Vector3 lastPos;
        Transform root, hips, spine, chest, neck, head, hat, tail, tail2, stache, pouch, shell;
        Transform armL, elbowL, handL, armR, elbowR, handR, legL, kneeL, footL, legR, kneeR, footR, leg2L, leg2R, stalkL, stalkR;
        Transform[,] tents;
        Vector3 hipsRest;

        void Awake()
        {
            if (model == null) model = GetComponentInChildren<ClayModel>();
            jitterSeed = Random.value * 100f;
            Bind();
            lastPos = transform.position;
        }

        public void Bind()
        {
            if (model == null) return;
            Transform B(string n) => model.Bone(n);
            root = B("root"); hips = B("hips"); spine = B("spine"); chest = B("chest"); neck = B("neck"); head = B("head");
            hat = B("hat"); tail = B("tail"); tail2 = B("tail2"); stache = B("stache"); pouch = B("pouch"); shell = B("shell");
            armL = B("arm_L"); elbowL = B("elbow_L"); handL = B("hand_L"); armR = B("arm_R"); elbowR = B("elbow_R"); handR = B("hand_R");
            legL = B("leg_L"); kneeL = B("knee_L"); footL = B("foot_L"); legR = B("leg_R"); kneeR = B("knee_R"); footR = B("foot_R");
            leg2L = B("leg2_L"); leg2R = B("leg2_R"); stalkL = B("stalk_L"); stalkR = B("stalk_R");
            if (hips) hipsRest = hips.localPosition;
            tents = new Transform[8, 4];
            for (int i = 0; i < 8; i++) for (int j = 0; j < 4; j++) tents[i, j] = B($"tent{i}_{j}");
        }

        public void Play(Gesture g, float seconds = 1.2f)
        {
            gesture = g;
            gestureT = 0f;
            gestureLen = seconds;
        }

        public bool Busy => gesture != Gesture.None;

        void LateUpdate()
        {
            if (model == null) return;
            // auto speed from movement if nobody set it
            if (!ClayClock.SteppedThisFrame) return;
            float dt = ClayClock.StepDt;
            idleT += dt;
            if (talking) talkT += dt;
            if (gesture != Gesture.None)
            {
                gestureT += dt;
                if (gestureT >= gestureLen) gesture = Gesture.None;
            }
            walkPhase += speed * dt / Mathf.Max(0.1f, stride);
            Pose();
        }

        static Quaternion E(float x, float y, float z) => Quaternion.Euler(x, y, z);

        float J(float k) => (Mathf.PerlinNoise(jitterSeed + k * 13.1f, ClayClock.Frame * 0.71f) - 0.5f) * 2f;

        void R(Transform t, Quaternion q) { if (t != null) t.localRotation = q; }

        void Pose()
        {
            float walk = Mathf.Clamp01(speed / 1.2f);
            float run = Mathf.Clamp01((speed - 2.2f) / 2f);
            float ph = walkPhase * Mathf.PI;               // one stride = half a cycle per leg
            float s = Mathf.Sin(ph), c = Mathf.Cos(ph);
            float breathe = Mathf.Sin(idleT * 2.1f) * (1f - walk);
            float shift = Mathf.Sin(idleT * 0.45f) * sway * (1f - walk);
            float jit = 0.9f;   // degrees of hand-posed wobble

            // body: bob twice per cycle, lean into speed, waddle side to side
            float bob = Mathf.Abs(s) * (0.018f + run * 0.03f) * walk;
            float squash = 1f + breathe * 0.012f - bob * 0.6f;
            if (hips)
            {
                hips.localPosition = hipsRest + new Vector3(shift * 0.01f, bob - (1f - Mathf.Abs(s)) * 0.008f * walk, 0f);
                hips.localRotation = E(walk * (4f + run * 8f) + J(1) * jit, s * 6f * walk + shift * 2f, c * 5f * walk * (1f - run * 0.5f) + shift * 1.5f);
                hips.localScale = new Vector3(1f / Mathf.Sqrt(squash), squash, 1f / Mathf.Sqrt(squash));
            }
            R(spine, E(breathe * 1.2f + J(2) * jit, -s * 4f * walk, -c * 3f * walk));
            R(chest, E(breathe * 1.5f + run * 6f, -s * 3f * walk, J(3) * jit));

            // head: keep level-ish, nod while talking, look around when idle
            float talkNod = talking ? Mathf.Sin(talkT * 7.3f) * 4f + Mathf.Sin(talkT * 2.9f) * 3f : 0f;
            float lookAround = (1f - walk) * (Mathf.PerlinNoise(jitterSeed, idleT * 0.15f) - 0.5f) * 40f * sway;
            R(neck, E(-walk * 3f + talkNod * 0.4f, lookAround * 0.4f, 0));
            R(head, E(-walk * 2f + talkNod + breathe * 1.0f + J(4) * jit, lookAround * 0.6f + s * 3f * walk, -c * 2f * walk + J(5) * jit));
            R(hat, E(-bob * 60f, 0, c * 2f * walk));

            // arms: swing opposite to legs, a little out from the body; talk gestures when idle
            float armSwing = 28f * walk * (1f + run * 0.6f);
            float gL = 0f, gR = 0f;
            if (talking && walk < 0.3f)
            {
                gR = (Mathf.Sin(talkT * 3.1f) * 0.5f + 0.5f) * 35f * personality;
                gL = (Mathf.Sin(talkT * 2.3f + 1.3f) * 0.5f + 0.5f) * 18f * personality;
            }
            R(armL, E(s * armSwing - gL * 0.6f + J(6) * jit, 0, -8f - shift * 2f - gL * 0.5f));
            R(armR, E(-s * armSwing - gR * 0.6f + J(7) * jit, 0, 8f - shift * 2f + gR * 0.5f));
            R(elbowL, E(-10f * walk - gL * 0.8f - run * 30f, 0, 0));
            R(elbowR, E(-10f * walk - gR * 0.8f - run * 30f, 0, 0));
            R(handL, E(J(8) * jit * 2f, 0, 0));
            R(handR, E(J(9) * jit * 2f, 0, 0));

            // legs: swing, knee bend on the passing pose, feet flex
            float legSwing = 30f * walk * (1f + run * 0.3f);
            float kL = Mathf.Max(0f, -s) * 40f * walk, kR = Mathf.Max(0f, s) * 40f * walk;
            R(legL, E(-s * legSwing, 0, -shift * 1.5f));
            R(legR, E(s * legSwing, 0, -shift * 1.5f));
            R(kneeL, E(kL, 0, 0));
            R(kneeR, E(kR, 0, 0));
            R(footL, E(s * legSwing * 0.5f - kL * 0.4f, 0, 0));
            R(footR, E(-s * legSwing * 0.5f - kR * 0.4f, 0, 0));
            R(leg2L, E(s * legSwing, 0, 0));
            R(leg2R, E(-s * legSwing, 0, 0));

            // tails, stalks, moustache, pouch, shell, tentacles: secondary motion
            R(tail, E(-5f + breathe * 2f, s * 14f * walk + Mathf.Sin(idleT * 1.7f) * 6f * sway, 0));
            R(tail2, E(-4f, s * 18f * walk + Mathf.Sin(idleT * 1.7f - 0.8f) * 8f * sway, 0));
            R(stalkL, E(Mathf.Sin(idleT * 3.1f) * 8f + J(10) * 3f, Mathf.Sin(idleT * 1.3f) * 10f, 0));
            R(stalkR, E(Mathf.Sin(idleT * 2.7f + 1f) * 8f + J(11) * 3f, Mathf.Sin(idleT * 1.1f + 2f) * 10f, 0));
            if (pouch) pouch.localScale = new Vector3(1f, 1f + Mathf.Sin(idleT * 2.4f) * 0.04f + bob * 2f, 1f);
            R(shell, E(walk * 3f + J(12) * jit, s * 3f * walk, c * 4f * walk));
            for (int i = 0; i < 8; i++)
                for (int j = 0; j < 4; j++)
                {
                    var t = tents[i, j];
                    if (t == null) continue;
                    float w = Mathf.Sin(idleT * 2.2f + i * 0.8f - j * 0.9f + walkPhase * 2f) * (10f + j * 6f) * (0.6f + walk);
                    t.localRotation = E(w * 0.6f + (j == 0 ? -6f : 4f), w * 0.4f, 0);
                }

            Activities();
            Gestures();
        }

        void Activities()
        {
            float p = activityPhase;
            switch (activity)
            {
                case Activity.Helm:
                    R(armL, E(-55f, 0, -15f)); R(armR, E(-55f, 0, 15f));
                    R(elbowL, E(-40f + Mathf.Sin(idleT * 1.3f) * 6f, 0, 0)); R(elbowR, E(-40f - Mathf.Sin(idleT * 1.3f) * 6f, 0, 0));
                    break;
                case Activity.Cast:
                    // wind up behind the head, then whip forward
                    float swing = p < 0.5f ? Mathf.Lerp(0f, -150f, p * 2f) : Mathf.Lerp(-150f, -50f, (p - 0.5f) * 2f);
                    R(armR, E(swing, 0, 10f)); R(elbowR, E(-30f, 0, 0));
                    R(chest, E(p < 0.5f ? -10f : 12f, 20f, 0));
                    break;
                case Activity.Reel:
                    R(armR, E(-40f + Mathf.Sin(idleT * 12f) * 12f, 0, 12f)); R(elbowR, E(-50f, 0, 0));
                    R(armL, E(-50f, 0, -10f)); R(elbowL, E(-45f, 0, 0));
                    R(chest, E(-6f, 0, 0));
                    break;
                case Activity.Haul:
                case Activity.Crank:
                    float pull = Mathf.Sin(p * Mathf.PI * 2f);
                    R(armL, E(-60f + pull * 25f, 0, -10f)); R(armR, E(-60f - pull * 25f, 0, 10f));
                    R(elbowL, E(-50f - pull * 15f, 0, 0)); R(elbowR, E(-50f + pull * 15f, 0, 0));
                    R(spine, E(10f - pull * 6f, 0, 0));
                    break;
                case Activity.Hammer:
                    float hit = p < 0.6f ? Mathf.Lerp(0f, -160f, p / 0.6f) : Mathf.Lerp(-160f, -20f, (p - 0.6f) / 0.4f);
                    R(armR, E(hit, 0, 8f)); R(armL, E(hit * 0.9f, 0, -8f));
                    R(elbowR, E(-20f, 0, 0)); R(elbowL, E(-20f, 0, 0));
                    R(spine, E(p < 0.6f ? -12f : 18f, 0, 0));
                    break;
                case Activity.Carry:
                    R(armL, E(-75f, 0, -18f)); R(armR, E(-75f, 0, 18f));
                    R(elbowL, E(-35f, 0, 0)); R(elbowR, E(-35f, 0, 0));
                    break;
                case Activity.Serve:
                    R(armR, E(-70f + Mathf.Sin(idleT * 3f) * 5f, 0, 6f)); R(elbowR, E(-25f, 0, 0));
                    break;
                case Activity.Sleep:
                    R(neck, E(25f, 0, 8f)); R(head, E(15f, 10f, 10f));
                    break;
                case Activity.Sit:
                    R(legL, E(-80f, 0, 0)); R(legR, E(-80f, 0, 0)); R(kneeL, E(80f, 0, 0)); R(kneeR, E(80f, 0, 0));
                    break;
            }
        }

        void Gestures()
        {
            if (gesture == Gesture.None) return;
            float t = Mathf.Clamp01(gestureT / gestureLen);
            float env = Mathf.Sin(t * Mathf.PI);   // in and out
            float a = personality;
            switch (gesture)
            {
                case Gesture.Wave:
                    R(armR, E(-20f, 0, 150f * env * a)); R(elbowR, E(0, 0, Mathf.Sin(gestureT * 16f) * 25f * env));
                    break;
                case Gesture.Hop:
                    if (hips) hips.localPosition += Vector3.up * Mathf.Max(0f, Mathf.Sin(t * Mathf.PI)) * 0.12f * a;
                    if (hips) hips.localScale = new Vector3(1f + (t < 0.15f || t > 0.85f ? 0.08f : -0.04f), t < 0.15f || t > 0.85f ? 0.88f : 1.08f, 1f);
                    R(armL, E(-30f * env, 0, -60f * env)); R(armR, E(-30f * env, 0, 60f * env));
                    break;
                case Gesture.Cheer:
                    R(armL, E(-10f, 0, -150f * env * a)); R(armR, E(-10f, 0, 150f * env * a));
                    if (hips) hips.localPosition += Vector3.up * Mathf.Abs(Mathf.Sin(t * Mathf.PI * 2f)) * 0.06f;
                    break;
                case Gesture.Shrug:
                    R(armL, E(-20f * env, 0, -35f * env)); R(armR, E(-20f * env, 0, 35f * env));
                    R(elbowL, E(-70f * env, 0, 0)); R(elbowR, E(-70f * env, 0, 0));
                    R(head, E(0, 0, 12f * env));
                    break;
                case Gesture.Nod:
                    R(head, E(Mathf.Sin(t * Mathf.PI * 4f) * 14f * env, 0, 0));
                    break;
                case Gesture.Shake:
                    R(head, E(0, Mathf.Sin(t * Mathf.PI * 5f) * 18f * env, 0));
                    break;
                case Gesture.Think:
                    R(armR, E(-95f * env, 0, 18f * env)); R(elbowR, E(-110f * env, 0, 0));
                    R(head, E(-6f * env, 0, -10f * env));
                    break;
                case Gesture.Droop:
                    R(chest, E(14f * env, 0, 0)); R(neck, E(14f * env, 0, 0)); R(head, E(10f * env, 0, 0));
                    R(armL, E(5f, 0, -2f)); R(armR, E(5f, 0, 2f));
                    break;
                case Gesture.Point:
                    R(armR, E(-85f * env, 20f * env, 10f)); R(elbowR, E(-5f, 0, 0));
                    break;
                case Gesture.Bow:
                    R(spine, E(25f * env, 0, 0)); R(chest, E(15f * env, 0, 0)); R(head, E(10f * env, 0, 0));
                    break;
            }
        }
    }
}
