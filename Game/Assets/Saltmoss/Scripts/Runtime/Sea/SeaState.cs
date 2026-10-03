using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The sea: owns the Gerstner wave set (shared with Saltmoss/ClaySea through globals), evaluates the same surface
    /// on the CPU for buoyancy, keeps a radial sea mesh centred under the camera, and gathers foam points (wakes,
    /// splashes) for the shader. Waves are evaluated at <see cref="ClayClock.StepTime"/>, so the sea moves on twos.
    /// </summary>
    [ExecuteAlways]
    public class SeaState : MonoBehaviour
    {
        public static SeaState I { get; private set; }

        public Material seaMaterial;
        public Vector2 roughCentre = new Vector2(0f, 75f);   // harbour mouth
        public float calmRadius = 30f, roughRadius = 650f;
        [Range(0, 1)] public float storm;
        public float calmMultiplier = 0.07f;
        public Vector2 windDir = new Vector2(-0.35f, -1f);   // waves roll in from the open sea toward the town

        const int N = 6;
        readonly Vector4[] waveA = new Vector4[N];
        readonly Vector4[] waveB = new Vector4[N];
        static readonly float[] Lambda = { 46f, 29f, 18.5f, 11.5f, 7.2f, 4.4f };
        static readonly float[] BaseAmp = { 0.34f, 0.24f, 0.16f, 0.1f, 0.06f, 0.035f };
        static readonly float[] Spread = { 0f, 24f, -31f, 47f, -58f, 75f };
        static readonly float[] Phase = { 0f, 1.7f, 4.1f, 2.9f, 5.3f, 0.8f };
        static readonly float[] Steep = { 0.35f, 0.4f, 0.45f, 0.5f, 0.5f, 0.55f };

        static readonly int IdA = Shader.PropertyToID("_SeaWaveA"), IdB = Shader.PropertyToID("_SeaWaveB");
        static readonly int IdRough = Shader.PropertyToID("_SeaRough"), IdRoughAmp = Shader.PropertyToID("_SeaRoughAmp");
        static readonly int IdFoam = Shader.PropertyToID("_FoamPoints");

        public float FarMultiplier => Mathf.Lerp(1.0f, 2.3f, storm);

        // foam points (x, z, radius, strength), refreshed every step
        static readonly List<Vector4> foamQueue = new List<Vector4>();
        readonly Vector4[] foam = new Vector4[32];

        Transform meshTf;
        Mesh seaMesh;

        void OnEnable()
        {
            I = this;
            BuildWaves();
            Push();
        }

        void BuildWaves()
        {
            var w = windDir.normalized;
            float baseAng = Mathf.Atan2(w.y, w.x);
            for (int i = 0; i < N; i++)
            {
                float a = baseAng + Spread[i] * Mathf.Deg2Rad;
                float k = 2f * Mathf.PI / Lambda[i];
                float omega = Mathf.Sqrt(9.81f * k) * 0.8f;   // a touch slow: heavy, sculpted water
                waveA[i] = new Vector4(Mathf.Cos(a), Mathf.Sin(a), k, omega);
                // steepness Q normalised so crests never loop (sum Q*k*A <= 1 at the roughest)
                waveB[i] = new Vector4(BaseAmp[i], Steep[i], Phase[i], 0f);
            }
        }

        void Push()
        {
            Shader.SetGlobalVectorArray(IdA, waveA);
            Shader.SetGlobalVectorArray(IdB, waveB);
            Shader.SetGlobalVector(IdRough, new Vector4(roughCentre.x, roughCentre.y, calmRadius, roughRadius));
            Shader.SetGlobalVector(IdRoughAmp, new Vector4(calmMultiplier, FarMultiplier, 0f, 0f));
        }

        /// <summary>Wave amplitude multiplier at a world xz (0.07 in the harbour .. ~2.3 in a far storm).</summary>
        public float RoughAt(float x, float z)
        {
            float d = Vector2.Distance(new Vector2(x, z), roughCentre);
            float t = Mathf.Clamp01((d - calmRadius) / Mathf.Max(roughRadius - calmRadius, 1f));
            t = t * t * (3f - 2f * t);
            return Mathf.Lerp(calmMultiplier, FarMultiplier, t);
        }

        /// <summary>0..1 how rough the open water is here (for gameplay: drama, hauling difficulty).</summary>
        public float Roughness01(Vector3 p) => Mathf.InverseLerp(calmMultiplier, 2.3f, RoughAt(p.x, p.z));

        Vector3 Displace(float x, float z, float t, out Vector3 normal)
        {
            float m = RoughAt(x, z);
            Vector3 d = Vector3.zero;
            Vector3 n = Vector3.up;
            for (int i = 0; i < N; i++)
            {
                var A = waveA[i];
                var B = waveB[i];
                float amp = B.x * m, q = B.y;
                float th = A.z * (A.x * x + A.y * z) - A.w * t + B.z;
                float s = Mathf.Sin(th), c = Mathf.Cos(th);
                d += new Vector3(q * amp * A.x * c, amp * s, q * amp * A.y * c);
                n -= new Vector3(A.x * A.z * amp * c, q * A.z * amp * s, A.y * A.z * amp * c);
            }
            normal = n.normalized;
            return d;
        }

        /// <summary>Sea surface height and normal at world xz (matches the shader; evaluated at stop-motion time).</summary>
        public float HeightAt(float x, float z, out Vector3 normal, bool stepped = true)
        {
            float t = stepped ? ClayClock.StepTime : Time.time;
            // find the rest point whose displaced position lands on (x, z)
            float rx = x, rz = z;
            for (int it = 0; it < 3; it++)
            {
                var dd = Displace(rx, rz, t, out _);
                rx = x - dd.x;
                rz = z - dd.z;
            }
            var d = Displace(rx, rz, t, out normal);
            return d.y;
        }

        public float HeightAt(float x, float z) => HeightAt(x, z, out _);

        public static void AddFoam(Vector3 p, float radius, float strength)
        {
            if (foamQueue.Count < 64) foamQueue.Add(new Vector4(p.x, p.z, radius, strength));
        }

        void Update()
        {
            if (I != this) I = this;
            Push();
            FollowCamera();
        }

        void LateUpdate()
        {
            if (!Application.isPlaying) return;
            if (ClayClock.SteppedThisFrame)
            {
                // keep the strongest 32 points
                foamQueue.Sort((a, b) => b.w.CompareTo(a.w));
                for (int i = 0; i < foam.Length; i++) foam[i] = i < foamQueue.Count ? foamQueue[i] : Vector4.zero;
                Shader.SetGlobalVectorArray(IdFoam, foam);
            }
            foamQueue.Clear();
        }

        void FollowCamera()
        {
            if (seaMesh == null) BuildMesh();
            var cam = Camera.main;
            if (cam == null || meshTf == null) return;
            var p = cam.transform.position;
            const float snap = 0.5f;
            meshTf.position = new Vector3(Mathf.Round(p.x / snap) * snap, 0f, Mathf.Round(p.z / snap) * snap);
        }

        void BuildMesh()
        {
            var existing = transform.Find("SeaSurface");
            if (existing != null) meshTf = existing;
            else
            {
                var go = new GameObject("SeaSurface");
                go.transform.SetParent(transform, false);
                go.layer = 11;
                meshTf = go.transform;
                go.AddComponent<MeshFilter>();
                var mr = go.AddComponent<MeshRenderer>();
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                mr.receiveShadows = true;
            }
            seaMesh = RadialMesh(192, 0.45f, 1.045f, 1600f);
            seaMesh.hideFlags = HideFlags.DontSave;
            meshTf.GetComponent<MeshFilter>().sharedMesh = seaMesh;
            meshTf.GetComponent<MeshRenderer>().sharedMaterial = seaMaterial;
        }

        /// <summary>Polar grid: fine near the centre, rings growing geometrically to the horizon.</summary>
        static Mesh RadialMesh(int segs, float firstStep, float growth, float maxR)
        {
            var radii = new List<float> { 0f };
            float r = 0f, step = firstStep;
            while (r < maxR)
            {
                r += step;
                radii.Add(r);
                if (r > 6f) step *= growth;
            }
            var verts = new List<Vector3>();
            var tris = new List<int>();
            verts.Add(Vector3.zero);
            for (int ri = 1; ri < radii.Count; ri++)
                for (int s = 0; s < segs; s++)
                {
                    float a = (s + (ri % 2) * 0.5f) / segs * Mathf.PI * 2f;
                    verts.Add(new Vector3(Mathf.Cos(a) * radii[ri], 0f, Mathf.Sin(a) * radii[ri]));
                }
            for (int s = 0; s < segs; s++)
            {
                tris.Add(0);
                tris.Add(1 + (s + 1) % segs);
                tris.Add(1 + s);
            }
            for (int ri = 1; ri < radii.Count - 1; ri++)
            {
                int a0 = 1 + (ri - 1) * segs, b0 = 1 + ri * segs;
                for (int s = 0; s < segs; s++)
                {
                    int s1 = (s + 1) % segs;
                    int a = a0 + s, a1 = a0 + s1, b = b0 + s, b1 = b0 + s1;
                    tris.Add(a); tris.Add(a1); tris.Add(b1);
                    tris.Add(a); tris.Add(b1); tris.Add(b);
                }
            }
            var m = new Mesh { name = "SeaRadial", indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            m.SetVertices(verts);
            m.SetTriangles(tris, 0);
            m.RecalculateNormals();
            m.bounds = new Bounds(Vector3.zero, new Vector3(maxR * 2f, 20f, maxR * 2f));
            return m;
        }
    }
}
