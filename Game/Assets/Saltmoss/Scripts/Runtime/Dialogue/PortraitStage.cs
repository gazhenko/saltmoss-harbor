using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Saltmoss
{
    /// <summary>
    /// A little photo studio far below the set where each speaker's own clay puppet sits for its dialogue portrait:
    /// studio key/fill/rim lamps (rendering-layer isolated from the world's sun), a painted backdrop card, and a camera
    /// filming the bust into a RenderTexture. The puppet emotes and talks live, on twos — portraits are performances,
    /// not pictures.
    /// </summary>
    public class PortraitStage : MonoBehaviour
    {
        public static PortraitStage I { get; private set; }
        public const int Layer = 13;
        public const uint PortraitRenderingLayer = 1u << 1;
        public RenderTexture Texture { get; private set; }

        class Actor
        {
            public GameObject go;
            public ClayModel model;
            public FaceRig face;
            public CritterAnimator anim;
            public Transform bust;
            public float height;
        }

        readonly Dictionary<string, Actor> actors = new Dictionary<string, Actor>();
        Camera cam;
        Transform root;
        Renderer card;
        Material cardMat;
        string showing;
        Vector3 camLocal;

        public static PortraitStage Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("PortraitStage");
            go.transform.position = new Vector3(0f, -600f, 0f);
            DontDestroyOnLoad(go);
            I = go.AddComponent<PortraitStage>();
            I.Build();
            return I;
        }

        void Build()
        {
            root = transform;
            Texture = new RenderTexture(560, 560, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4, name = "PortraitRT" };
            var cgo = new GameObject("PortraitCamera");
            cgo.transform.SetParent(root, false);
            cam = cgo.AddComponent<Camera>();
            cam.cullingMask = 1 << Layer;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.8f, 0.75f, 0.65f);
            cam.fieldOfView = 22f;
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 20f;
            cam.targetTexture = Texture;
            cam.enabled = false;
            var data = cgo.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            data.volumeLayerMask = 1 << Layer;
            data.antialiasing = AntialiasingMode.None;
            data.renderShadows = false;

            // studio lamps: warm key, cool fill, bright rim — they light only the portrait rendering layer
            Lamp("Key", new Vector3(0.9f, 1.1f, 1.4f), new Color(1f, 0.92f, 0.82f), 3.2f, 6f);
            Lamp("Fill", new Vector3(-1.3f, 0.4f, 1.2f), new Color(0.75f, 0.85f, 1f), 1.3f, 6f);
            Lamp("Rim", new Vector3(-0.6f, 1.3f, -1.2f), new Color(1f, 0.95f, 0.9f), 2.6f, 5f);

            // painted backdrop card
            var cardGo = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Destroy(cardGo.GetComponent<Collider>());
            cardGo.name = "Backcloth";
            cardGo.layer = Layer;
            cardGo.transform.SetParent(root, false);
            card = cardGo.GetComponent<Renderer>();
            card.shadowCastingMode = ShadowCastingMode.Off;
            card.renderingLayerMask = PortraitRenderingLayer;
            var src = FindClayMaterial();
            cardMat = src != null ? new Material(src) : new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            cardMat.SetFloat("_RestFromUV1", 0f);
            cardMat.SetFloat("_VertexColor", 0f);
            cardMat.SetFloat("_BoilAmp", 0f);
            cardMat.SetFloat("_FingerScale", 3f);
            card.sharedMaterial = cardMat;

            // its own grade: tonemapping, a soft vignette, grain — no depth of field
            var vgo = new GameObject("PortraitGrade") { layer = Layer };
            vgo.transform.SetParent(root, false);
            var vol = vgo.AddComponent<Volume>();
            vol.isGlobal = true;
            var prof = ScriptableObject.CreateInstance<VolumeProfile>();
            prof.Add<Tonemapping>(true).mode.Override(TonemappingMode.ACES);
            var vig = prof.Add<Vignette>(true); vig.intensity.Override(0.32f); vig.smoothness.Override(0.5f);
            var gr = prof.Add<FilmGrain>(true); gr.intensity.Override(0.25f); gr.type.Override(FilmGrainLookup.Medium2);
            var ca = prof.Add<ColorAdjustments>(true); ca.contrast.Override(8f); ca.postExposure.Override(0.25f);
            vol.sharedProfile = prof;
        }

        static Material FindClayMaterial()
        {
            foreach (var r in FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
                if (r.sharedMaterial != null && r.sharedMaterial.shader != null && r.sharedMaterial.shader.name == "Saltmoss/Clay") return r.sharedMaterial;
            var any = ModelBank.I.Get("chars/pip");
            var rr = any != null ? any.GetComponentInChildren<Renderer>(true) : null;
            return rr != null ? rr.sharedMaterial : null;
        }

        void Lamp(string name, Vector3 pos, Color c, float intensity, float range)
        {
            var go = new GameObject(name);
            go.transform.SetParent(root, false);
            go.transform.localPosition = pos;
            var l = go.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = c;
            l.intensity = intensity;
            l.range = range;
            l.shadows = LightShadows.None;
            l.renderingLayerMask = (int)PortraitRenderingLayer;
        }

        Actor Get(string id)
        {
            if (actors.TryGetValue(id, out var a)) return a;
            var member = Cast.Get(id);
            var go = ModelBank.I.Spawn(member.model, root.position, Quaternion.identity, root);
            SetLayer(go.transform);
            a = new Actor { go = go, model = go.GetComponent<ClayModel>() };
            a.face = go.AddComponent<FaceRig>();
            a.face.model = a.model;
            a.face.Bind();
            a.anim = go.AddComponent<CritterAnimator>();
            a.anim.model = a.model;
            a.anim.personality = member.personality;
            a.anim.sway = 0.4f;
            a.anim.Bind();
            a.bust = a.model != null ? a.model.Socket("bust") : null;
            a.height = a.model != null ? a.model.VisualBounds().size.y : 1f;
            go.SetActive(false);
            actors[id] = a;
            return a;
        }

        static void SetLayer(Transform t)
        {
            t.gameObject.layer = Layer;
            var r = t.GetComponent<Renderer>();
            if (r != null)
            {
                r.renderingLayerMask = PortraitRenderingLayer;
                r.shadowCastingMode = ShadowCastingMode.Off;
            }
            foreach (Transform c in t) SetLayer(c);
        }

        public FaceRig Face(string id) => Get(id).face;
        public CritterAnimator Anim(string id) => Get(id).anim;

        public void Show(string id)
        {
            if (string.IsNullOrEmpty(id)) { Hide(); return; }
            foreach (var kv in actors) kv.Value.go.SetActive(kv.Key == id);
            var a = Get(id);
            a.go.SetActive(true);
            showing = id;
            var member = Cast.Get(id);
            Vector3 bust = a.bust != null ? a.bust.position : root.position + Vector3.up * a.height * 0.75f;
            float vis = (0.26f + 0.28f * a.height) * member.portraitDistance;
            float dist = vis / (2f * Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad));
            var dir = Quaternion.Euler(0f, 16f, 0f) * Vector3.forward;
            cam.transform.position = bust + dir * dist + Vector3.up * vis * 0.06f;
            cam.transform.rotation = Quaternion.LookRotation(bust - cam.transform.position + Vector3.down * vis * 0.04f);
            card.transform.position = bust - dir * 1.6f;
            card.transform.rotation = Quaternion.LookRotation(-dir);
            card.transform.localScale = Vector3.one * (vis * 3.2f);
            cardMat.SetColor("_BaseColor", member.backdrop);
            cam.enabled = true;
        }

        public void Hide()
        {
            showing = null;
            if (cam != null) cam.enabled = false;
            foreach (var kv in actors) kv.Value.go.SetActive(false);
        }
    }
}
