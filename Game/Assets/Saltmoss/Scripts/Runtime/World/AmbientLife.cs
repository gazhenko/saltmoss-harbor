using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Life around the set: gulls wheeling over the harbour (puppets on wires, flapping on twos), cotton smoke from
    /// every chimney and stovepipe, and the odd gull cry and buoy bell.
    /// </summary>
    public class AmbientLife : MonoBehaviour
    {
        class Gull { public Transform t; public ClayModel m; public float r, h, speed, phase; public Vector3 c; }
        readonly List<Gull> gulls = new List<Gull>();
        readonly List<Transform> chimneys = new List<Transform>();
        float smokeTimer, cryTimer = 6f, bellTimer = 9f;

        void Start()
        {
            foreach (var m in FindObjectsByType<ClayModel>(FindObjectsSortMode.None))
                foreach (var s in m.sockets)
                    if (s != null && (s.name.Contains("chimney") || s.name.Contains("smoke") || s.name.Contains("stovepipe")) && !s.GetComponentInParent<BoatController>())
                        chimneys.Add(s);
            for (int i = 0; i < 6; i++)
            {
                var go = ModelBank.I.Spawn(i % 3 == 2 ? "chars/cust_gull_b" : "chars/cust_gull", Vector3.zero, Quaternion.identity, transform);
                go.transform.localScale = Vector3.one * 0.55f;
                foreach (var r in go.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                gulls.Add(new Gull { t = go.transform, m = go.GetComponent<ClayModel>(), r = Random.Range(14f, 34f), h = Random.Range(11f, 22f), speed = Random.Range(0.25f, 0.45f) * (i % 2 == 0 ? 1 : -1), phase = Random.value * 6.28f, c = new Vector3(Random.Range(-15f, 15f), 0f, Random.Range(0f, 40f)) });
            }
        }

        void Update()
        {
            var D = GameState.D;
            if (ClayClock.SteppedThisFrame)
            {
                float t = ClayClock.StepTime;
                foreach (var g in gulls)
                {
                    float a = g.phase + t * g.speed;
                    var p = g.c + new Vector3(Mathf.Cos(a) * g.r, g.h + Mathf.Sin(a * 2.3f) * 1.5f, Mathf.Sin(a) * g.r);
                    var fwd = new Vector3(-Mathf.Sin(a), 0f, Mathf.Cos(a)) * Mathf.Sign(g.speed);
                    g.t.SetPositionAndRotation(p, Quaternion.LookRotation(fwd) * Quaternion.Euler(10f, 0f, -18f * Mathf.Sign(g.speed)));
                    if (g.m == null) continue;
                    float flap = Mathf.Sin(t * 9f + g.phase) * 55f;
                    var l = g.m.Bone("arm_L");
                    var r = g.m.Bone("arm_R");
                    if (l) l.localRotation = Quaternion.Euler(0, 0, -95f - flap);
                    if (r) r.localRotation = Quaternion.Euler(0, 0, 95f + flap);
                    var lf = g.m.Bone("leg_L"); var rf = g.m.Bone("leg_R");
                    if (lf) lf.localRotation = Quaternion.Euler(70f, 0, 0);
                    if (rf) rf.localRotation = Quaternion.Euler(70f, 0, 0);
                }
            }
            smokeTimer -= Time.deltaTime;
            if (smokeTimer <= 0f && chimneys.Count > 0)
            {
                smokeTimer = 0.35f;
                var c = chimneys[Random.Range(0, chimneys.Count)];
                if (Camera.main != null && Vector3.Distance(Camera.main.transform.position, c.position) < 140f)
                    CottonPuff.Emit(c.position, new Color(0.8f, 0.78f, 0.76f), 0.35f, new Vector3(0f, 0.6f, 0f), 3.2f);
            }
            var cam = Camera.main;
            if (cam == null) return;
            cryTimer -= Time.deltaTime;
            if (cryTimer <= 0f && gulls.Count > 0)
            {
                cryTimer = Random.Range(5f, 14f);
                var g = gulls[Random.Range(0, gulls.Count)];
                AudioDirector.Play("gull", g.t.position, 0.7f, 0.12f);
            }
            bellTimer -= Time.deltaTime;
            if (bellTimer <= 0f)
            {
                bellTimer = Random.Range(12f, 26f);
                AudioDirector.Play("buoy_bell", new Vector3(0f, 1f, 80f), 0.6f, 0.05f);
            }
        }
    }
}
