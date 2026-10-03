using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Cotton-wool puffs (smoke, steam, spray): a tuft of wool on a wire that the animator nudges up and along the
    /// wind each exposure, teasing it bigger and then pinching it away. Pooled.
    /// </summary>
    public class CottonPuff : MonoBehaviour
    {
        static readonly List<CottonPuff> pool = new List<CottonPuff>();
        static Transform poolRoot;
        public static Vector3 Wind = new Vector3(-0.6f, 0f, -0.4f);

        float age, life, size;
        Vector3 vel;
        Renderer rend;
        MaterialPropertyBlock mpb;
        static readonly int IdColor = Shader.PropertyToID("_BaseColor");

        public static void Emit(Vector3 pos, Color color, float size, Vector3? velocity = null, float life = 2.6f)
        {
            CottonPuff p = null;
            foreach (var q in pool) if (!q.gameObject.activeSelf) { p = q; break; }
            if (p == null)
            {
                if (pool.Count >= 60) return;
                p = Create();
                if (p == null) return;
            }
            p.transform.position = pos;
            p.transform.rotation = Random.rotation;
            p.age = 0f;
            p.life = life * Random.Range(0.8f, 1.2f);
            p.size = size;
            p.vel = velocity ?? new Vector3(0f, 0.9f, 0f) + Random.insideUnitSphere * 0.15f;
            p.mpb.SetColor(IdColor, color);
            p.rend.SetPropertyBlock(p.mpb);
            p.transform.localScale = Vector3.one * size * 0.3f;
            p.gameObject.SetActive(true);
        }

        static CottonPuff Create()
        {
            if (poolRoot == null) { poolRoot = new GameObject("CottonPuffs").transform; }
            int v = Random.Range(1, 4);
            GameObject go = ModelBank.I.Get("town/smoke_puff_" + v) != null
                ? ModelBank.I.Spawn("town/smoke_puff_" + v, Vector3.zero, Quaternion.identity, poolRoot)
                : null;
            if (go == null)
            {
                go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                Destroy(go.GetComponent<Collider>());
                go.transform.SetParent(poolRoot, false);
                var mat = Resources.Load<Material>("Cotton");
                if (mat != null)
                {
                    var m = new Material(mat);
                    m.SetFloat("_RestFromUV1", 0f);
                    m.SetFloat("_VertexColor", 0f);
                    go.GetComponent<Renderer>().sharedMaterial = m;
                }
            }
            go.name = "Puff";
            var p = go.AddComponent<CottonPuff>();
            p.rend = go.GetComponentInChildren<Renderer>();
            p.mpb = new MaterialPropertyBlock();
            foreach (var r in go.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            pool.Add(p);
            return p;
        }

        void Update()
        {
            if (!ClayClock.SteppedThisFrame) return;
            float dt = ClayClock.StepDt;
            age += dt;
            float k = age / life;
            if (k >= 1f) { gameObject.SetActive(false); return; }
            vel += Wind * dt * 0.6f;
            vel *= 0.97f;
            transform.position += vel * dt;
            float grow = k < 0.6f ? Mathf.Lerp(0.3f, 1f, k / 0.6f) : Mathf.Lerp(1f, 0.05f, (k - 0.6f) / 0.4f);
            transform.localScale = Vector3.one * size * grow;
            transform.Rotate(Random.insideUnitSphere * 12f);
        }
    }
}
