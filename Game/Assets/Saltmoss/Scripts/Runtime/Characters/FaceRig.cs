using System;
using UnityEngine;

namespace Saltmoss
{
    public enum Expr { Neutral, Happy, Laugh, Surprised, Sad, Worried, Angry, Smug, Thinking, Sleepy, Determined }

    /// <summary>
    /// Stop-motion face: replacement mouths, replacement eyelids/happy eyes, brow poses, pupils and blush, exactly as
    /// an animator would swap and nudge clay pieces between exposures. Talking flaps the mouth (or the jaw for beaks)
    /// on each voice-blip syllable. Only changes on stop-motion steps.
    /// </summary>
    [DefaultExecutionOrder(8000)]
    public class FaceRig : MonoBehaviour
    {
        public ClayModel model;
        public Expr expression = Expr.Neutral;
        /// <summary>Point in world space the eyes look toward (null = straight ahead).</summary>
        public Transform lookTarget;
        public Vector3? lookPoint;

        Transform browL, browR, pupilL, pupilR, jaw, stache, mouthBone;
        Vector3 browLRest, browRRest, pupilLRest, pupilRRest;
        bool hasMouths;
        float blinkTimer = 2f;
        int blinkSteps;
        float syllable;       // 0..1 decays: current mouth openness from talking
        int syllableShape;
        float browBounce;
        public float JawOpen { get; private set; }
        static readonly string[] Mouths = { "mouth_neutral", "mouth_smile", "mouth_open", "mouth_o", "mouth_frown", "mouth_grin", "mouth_wavy" };

        public static Expr Parse(string s)
        {
            return Enum.TryParse<Expr>(s, true, out var e) ? e : Expr.Neutral;
        }

        void Awake()
        {
            if (model == null) model = GetComponentInChildren<ClayModel>();
            Bind();
        }

        public void Bind()
        {
            if (model == null) return;
            browL = model.Bone("brow_L"); browR = model.Bone("brow_R");
            pupilL = model.Bone("pupil_L"); pupilR = model.Bone("pupil_R");
            jaw = model.Bone("jaw"); stache = model.Bone("stache"); mouthBone = model.Bone("mouth");
            if (browL) browLRest = browL.localPosition;
            if (browR) browRRest = browR.localPosition;
            if (pupilL) pupilLRest = pupilL.localPosition;
            if (pupilR) pupilRRest = pupilR.localPosition;
            hasMouths = model.HasPiece("mouth_smile");
        }

        /// <summary>Called per voice blip: open the mouth for a syllable (vowel shape picks o/open).</summary>
        public void Syllable(char c, float loud = 1f)
        {
            syllable = Mathf.Clamp01(0.55f + loud * 0.45f);
            char l = char.ToLowerInvariant(c);
            syllableShape = l == 'o' || l == 'u' || l == 'w' ? 1 : l == 'e' || l == 'i' || l == 'y' ? 2 : 0;
        }

        public void Bounce() => browBounce = 1f;

        void LateUpdate()
        {
            if (model == null || !ClayClock.SteppedThisFrame) return;
            float dt = ClayClock.StepDt;
            Pose(dt);
            syllable = Mathf.MoveTowards(syllable, 0f, dt * 5.5f);
            browBounce = Mathf.MoveTowards(browBounce, 0f, dt * 4f);
        }

        struct P
        {
            public float innerL, innerR, lift;      // brow: inner-end raise (deg), lift (fraction of eye radius)
            public int lids;                        // 0 none, 1 half, 2 closed, 3 happy arcs
            public int mouth;                       // index into Mouths
            public float pupil;                     // pupil scale
            public bool blush;
            public Vector2 look;                    // pupil offset bias
        }

        static P Params(Expr e)
        {
            switch (e)
            {
                case Expr.Happy: return new P { innerL = 6, innerR = 6, lift = 0.15f, mouth = 1, pupil = 1.08f };
                case Expr.Laugh: return new P { innerL = 10, innerR = 10, lift = 0.25f, lids = 3, mouth = 5, pupil = 1f, blush = true };
                case Expr.Surprised: return new P { innerL = 4, innerR = 4, lift = 0.55f, mouth = 3, pupil = 0.78f };
                case Expr.Sad: return new P { innerL = 20, innerR = 20, lift = 0.05f, lids = 1, mouth = 4, pupil = 1.1f, look = new Vector2(0, -0.4f) };
                case Expr.Worried: return new P { innerL = 16, innerR = 16, lift = 0.2f, mouth = 6, pupil = 0.95f };
                case Expr.Angry: return new P { innerL = -22, innerR = -22, lift = -0.1f, lids = 1, mouth = 4, pupil = 0.9f };
                case Expr.Smug: return new P { innerL = -6, innerR = 14, lift = 0.1f, lids = 1, mouth = 1, pupil = 1f, look = new Vector2(0.4f, 0) };
                case Expr.Thinking: return new P { innerL = -4, innerR = 14, lift = 0.15f, mouth = 6, pupil = 1f, look = new Vector2(0.5f, 0.6f) };
                case Expr.Sleepy: return new P { innerL = 4, innerR = 4, lift = -0.05f, lids = 1, mouth = 0, pupil = 1f, look = new Vector2(0, -0.3f) };
                case Expr.Determined: return new P { innerL = -12, innerR = -12, lift = 0.0f, mouth = 1, pupil = 1f };
                default: return new P { mouth = 0, pupil = 1f };
            }
        }

        void Pose(float dt)
        {
            var p = Params(expression);
            // blinks (not while eyes are already closed/happy)
            blinkTimer -= dt;
            if (blinkTimer <= 0f)
            {
                blinkSteps = UnityEngine.Random.value < 0.15f ? 3 : 2;   // sometimes a double-length blink
                blinkTimer = UnityEngine.Random.Range(2.2f, 5.5f);
            }
            int lids = p.lids;
            if (blinkSteps > 0 && lids < 2) { lids = 2; blinkSteps--; }

            bool happyEyes = lids == 3;
            for (int s = 0; s < 2; s++)
            {
                string side = s == 0 ? "_L" : "_R";
                model.Show("lidhalf" + side, lids == 1);
                model.Show("lidclosed" + side, lids == 2);
                model.Show("eyehappy" + side, happyEyes);
                model.Show("eyeball" + side, !happyEyes);
                model.Show("pupil" + side, !happyEyes && lids != 2);
                model.Show("blush" + side, p.blush);
            }

            // brows: rotate about their own pivot (inner end up = worried), lift for surprise, bounce on emphasis
            float eyeR = 0.04f * model.transform.lossyScale.y;
            float lift = (p.lift + browBounce * 0.25f) * eyeR * 1.4f;
            if (browL) { browL.localRotation = Quaternion.Euler(0, 0, p.innerL); browL.localPosition = browLRest + Vector3.up * lift; }
            if (browR) { browR.localRotation = Quaternion.Euler(0, 0, -p.innerR); browR.localPosition = browRRest + Vector3.up * lift; }

            // pupils: scale + look offset toward the target
            Vector2 look = p.look;
            Vector3? lp = lookTarget != null ? lookTarget.position : lookPoint;
            var head = model.Bone("head");
            if (lp.HasValue && head != null)
            {
                var local = head.InverseTransformPoint(lp.Value);
                look += new Vector2(Mathf.Clamp(local.x / Mathf.Max(0.3f, local.z), -1f, 1f), Mathf.Clamp(local.y / Mathf.Max(0.3f, local.z), -1f, 1f));
            }
            look = Vector2.ClampMagnitude(look, 1f);
            float off = 0.011f;
            if (pupilL) { pupilL.localScale = Vector3.one * p.pupil; pupilL.localPosition = pupilLRest + new Vector3(look.x, look.y, 0) * off; }
            if (pupilR) { pupilR.localScale = Vector3.one * p.pupil; pupilR.localPosition = pupilRRest + new Vector3(look.x, look.y, 0) * off; }

            // mouth: replacement pieces, swapped to open/o/grin on syllables
            int mouth = p.mouth;
            bool talking = syllable > 0.15f;
            if (talking)
            {
                if (syllableShape == 1) mouth = 3;
                else if (syllable > 0.5f) mouth = expression == Expr.Laugh || expression == Expr.Happy ? 5 : 2;
                else mouth = expression == Expr.Sad || expression == Expr.Angry ? 4 : 0;
            }
            if (hasMouths)
                for (int i = 0; i < Mouths.Length; i++) model.Show(Mouths[i], i == mouth);
            // jaw (beaks) and walrus moustache
            float jawOpen = talking ? syllable * (syllableShape == 1 ? 14f : 18f) : (expression == Expr.Surprised ? 8f : expression == Expr.Laugh ? 12f : 0f);
            JawOpen = jawOpen;
            if (jaw) jaw.localRotation = Quaternion.Euler(jawOpen, 0, 0);
            if (stache) stache.localRotation = Quaternion.Euler(-jawOpen * 0.35f, 0, 0);
            if (mouthBone && jaw == null) mouthBone.localScale = new Vector3(1f, 1f + syllable * 0.15f, 1f);
        }
    }
}
