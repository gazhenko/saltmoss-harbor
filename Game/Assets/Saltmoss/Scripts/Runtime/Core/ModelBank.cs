using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Model prefabs by id ("fish/herring"), built by the content pipeline (Resources/ModelBank).</summary>
    public class ModelBank : ScriptableObject
    {
        public string[] ids = new string[0];
        public GameObject[] prefabs = new GameObject[0];
        Dictionary<string, GameObject> map;
        static ModelBank inst;

        public static ModelBank I
        {
            get
            {
                if (inst == null) inst = Resources.Load<ModelBank>("ModelBank");
                if (inst == null) inst = CreateInstance<ModelBank>();
                return inst;
            }
        }

        public GameObject Get(string id)
        {
            if (map == null)
            {
                map = new Dictionary<string, GameObject>();
                for (int i = 0; i < ids.Length && i < prefabs.Length; i++) map[ids[i]] = prefabs[i];
            }
            return id != null && map.TryGetValue(id, out var g) ? g : null;
        }

        /// <summary>Instantiate a model (or a placeholder lump if it isn't built yet).</summary>
        public GameObject Spawn(string id, Vector3 pos, Quaternion rot, Transform parent = null)
        {
            var p = Get(id);
            GameObject go;
            if (p != null) go = Instantiate(p, pos, rot, parent);
            else
            {
                // not sculpted yet: an invisible stand-in keeps the systems running
                Debug.LogWarning("[ModelBank] missing model " + id);
                go = new GameObject();
                go.transform.SetPositionAndRotation(pos, rot);
                go.transform.SetParent(parent, true);
                go.AddComponent<ClayModel>();
            }
            go.name = id;
            return go;
        }

        public IEnumerable<string> Ids(string prefix)
        {
            foreach (var id in ids) if (id.StartsWith(prefix)) yield return id;
        }
    }
}
