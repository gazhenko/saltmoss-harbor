using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Saltmoss
{
    /// <summary>
    /// A turntable studio for catch: shows one model live (the "You caught…!" reveal, turning on twos) and bakes
    /// little transparent icons of every item for inventory grids, the shop display and the collection book.
    /// </summary>
    public class ItemStage : MonoBehaviour
    {
        public static ItemStage I { get; private set; }
        public const int Layer = 14;
        public const uint StageRenderingLayer = 1u << 2;

        Camera cam;
        Transform turntable;
        GameObject current;
        string currentId;
        public RenderTexture Live { get; private set; }
        RenderTexture iconRT;
        readonly Dictionary<string, Sprite> icons = new Dictionary<string, Sprite>();
        float spin;

        public static ItemStage Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("ItemStage");
            go.transform.position = new Vector3(40f, -700f, 0f);
            DontDestroyOnLoad(go);
            I = go.AddComponent<ItemStage>();
            I.Build();
            return I;
        }

        void Build()
        {
            Live = new RenderTexture(720, 720, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4, name = "ItemLiveRT" };
            iconRT = new RenderTexture(256, 256, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4, name = "ItemIconRT" };
            var cg = new GameObject("ItemCamera");
            cg.transform.SetParent(transform, false);
            cam = cg.AddComponent<Camera>();
            cam.cullingMask = 1 << Layer;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0, 0, 0, 0);
            cam.fieldOfView = 24f;
            cam.nearClipPlane = 0.02f;
            cam.farClipPlane = 30f;
            cam.enabled = false;
            var data = cg.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = false;
            data.renderShadows = false;
            turntable = new GameObject("Turntable").transform;
            turntable.SetParent(transform, false);
            Lamp(new Vector3(1.2f, 1.6f, 1.6f), new Color(1f, 0.94f, 0.86f), 2.6f);
            Lamp(new Vector3(-1.6f, 0.6f, 1.2f), new Color(0.8f, 0.88f, 1f), 1.1f);
            Lamp(new Vector3(-0.4f, 1.4f, -1.6f), Color.white, 1.8f);
        }

        void Lamp(Vector3 p, Color c, float i)
        {
            var go = new GameObject("Lamp");
            go.transform.SetParent(transform, false);
            go.transform.localPosition = p;
            var l = go.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = c;
            l.intensity = i;
            l.range = 8f;
            l.renderingLayerMask = (int)StageRenderingLayer;
        }

        GameObject Load(string modelId)
        {
            var go = ModelBank.I.Spawn(modelId, turntable.position, Quaternion.identity, turntable);
            SetLayer(go.transform);
            return go;
        }

        static void SetLayer(Transform t)
        {
            t.gameObject.layer = Layer;
            var r = t.GetComponent<Renderer>();
            if (r != null) { r.renderingLayerMask = StageRenderingLayer; r.shadowCastingMode = ShadowCastingMode.Off; }
            foreach (Transform c in t) SetLayer(c);
        }

        /// <summary>Frame a model: centre it on the turntable and back the camera off to fit its bounds.</summary>
        void Frame(GameObject go, float fill, float pitch = 14f)
        {
            var b = Bounds(go);
            go.transform.position += turntable.position - b.center;
            float r = b.extents.magnitude;
            float dist = r / Mathf.Sin(cam.fieldOfView * 0.5f * Mathf.Deg2Rad) * fill;
            cam.transform.position = turntable.position + Quaternion.Euler(-pitch, 0f, 0f) * Vector3.forward * dist;
            cam.transform.LookAt(turntable.position);
        }

        static Bounds Bounds(GameObject go)
        {
            var rs = go.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(go.transform.position, Vector3.one * 0.3f);
            var b = rs[0].bounds;
            foreach (var r in rs) b.Encapsulate(r.bounds);
            return b;
        }

        /// <summary>Start showing an item live (turning). Fish are shown side-on.</summary>
        public void ShowLive(ItemDef d)
        {
            Clear();
            if (d == null) return;
            currentId = d.id;
            current = Load(d.model);
            turntable.rotation = Quaternion.Euler(0f, d.kind == Kind.Fish ? 90f : 30f, 0f);
            Frame(current, 1.15f);
            var mr = current.GetComponentsInChildren<Renderer>();
            if (d.kind == Kind.Fish)
                foreach (var r in mr) { var m = r.material; m.SetFloat("_Wiggle", 0.03f); }
            cam.targetTexture = Live;
            cam.enabled = true;
            spin = 0f;
        }

        public void Clear()
        {
            if (current != null) Destroy(current);
            current = null;
            currentId = null;
            if (cam != null) cam.enabled = false;
        }

        void Update()
        {
            if (current == null || !ClayClock.SteppedThisFrame) return;
            spin += ClayClock.StepDt * 40f;
            turntable.rotation = Quaternion.Euler(0f, 90f + Mathf.Sin(spin * Mathf.Deg2Rad * 2f) * 35f, Mathf.Sin(spin * 0.05f) * 4f);
        }

        /// <summary>A cached transparent icon for an item (rendered the first time it's asked for).</summary>
        public Sprite Icon(string itemId)
        {
            if (itemId == null) return null;
            if (icons.TryGetValue(itemId, out var s)) return s;
            var d = Catalog.Get(itemId);
            if (d == null) return null;
            bool wasLive = cam.enabled;
            var live = current;
            if (live != null) live.SetActive(false);
            var go = Load(d.model);
            go.transform.rotation = Quaternion.Euler(0f, d.kind == Kind.Fish ? 90f : 35f, d.kind == Kind.Fish ? 8f : 0f);
            Frame(go, 1.05f, 22f);
            cam.targetTexture = iconRT;
            cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = iconRT;
            var tex = new Texture2D(256, 256, TextureFormat.RGBA32, false) { name = "icon_" + itemId };
            tex.ReadPixels(new Rect(0, 0, 256, 256), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            DestroyImmediate(go);
            if (live != null) { live.SetActive(true); Frame(live, 1.15f); cam.targetTexture = Live; }
            cam.enabled = wasLive;
            s = Sprite.Create(tex, new Rect(0, 0, 256, 256), new Vector2(0.5f, 0.5f), 100f);
            s.name = tex.name;
            icons[itemId] = s;
            return s;
        }
    }
}
