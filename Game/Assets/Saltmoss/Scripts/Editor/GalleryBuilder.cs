using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Saltmoss.EditorTools
{
    /// <summary>
    /// The Gallery scene: every imported model laid out on a clay tabletop by group (one row per group), lit like the
    /// game, for in-engine review shots (Tools/shots.sh gallery). Row origins are logged so -cam shots can frame them.
    /// </summary>
    public static class GalleryBuilder
    {
        public static readonly string[] Groups = { "chars", "boat", "fish", "crabs", "treasure", "junk", "town" };

        [MenuItem("Saltmoss/Scenes/Build Gallery")]
        public static void Build()
        {
            var scene = SceneKit.NewScene("Gallery");
            SceneKit.Lighting(15.5f);
            SceneKit.PostVolume();
            SceneKit.Backdrop();
            var sea = SceneKit.Sea();
            sea.roughCentre = new Vector2(0f, -400f);
            var root = new GameObject("Exhibits").transform;
            float z = 0f;
            foreach (var g in Groups)
            {
                var ids = SceneKit.ModelIds(g).ToList();
                if (ids.Count == 0) continue;
                float x = 0f, depth = 1.5f;
                var row = new GameObject("row_" + g).transform;
                row.SetParent(root, false);
                foreach (var id in ids)
                {
                    var go = SceneKit.Place(id, Vector3.zero, 180f, row);
                    if (go == null) continue;
                    var b = go.GetComponent<ClayModel>().VisualBounds();
                    float w = Mathf.Max(0.3f, b.size.x);
                    go.transform.position = new Vector3(x + w * 0.5f - (b.center.x - go.transform.position.x), 1.0f, z);
                    x += w + Mathf.Max(0.25f, w * 0.3f);
                    depth = Mathf.Max(depth, b.size.z + 1f);
                }
                Debug.Log($"[Gallery] row {g}: z={z:0.0} width={x:0.0} count={ids.Count}");
                SceneKit.Slab("table_" + g, new Vector3(x * 0.5f - 0.5f, 0.5f, z), new Vector3(x + 2f, 1f, depth + 1f), new Color(0.55f, 0.5f, 0.44f), row);
                z += depth + 2.5f;
            }
            SceneKit.MainCamera(new Vector3(3f, 2.4f, -5f), new Vector3(3f, 1.4f, 0f));
            SceneKit.Save(scene);
        }
    }
}
