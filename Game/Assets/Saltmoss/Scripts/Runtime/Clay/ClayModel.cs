using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Added by the .claymesh importer to every model root: name lookups for bones, pieces (incl. hidden replacement
    /// pieces such as mouth_smile or lidclosed_L) and sockets, plus each bone's rest pose.
    /// </summary>
    [DisallowMultipleComponent]
    public class ClayModel : MonoBehaviour
    {
        public Transform[] bones = new Transform[0];
        public GameObject[] pieces = new GameObject[0];
        public Transform[] sockets = new Transform[0];

        Dictionary<string, Transform> boneMap, socketMap;
        Dictionary<string, GameObject> pieceMap;
        Vector3[] restPos;
        Quaternion[] restRot;

        void Build()
        {
            if (boneMap != null) return;
            boneMap = new Dictionary<string, Transform>();
            socketMap = new Dictionary<string, Transform>();
            pieceMap = new Dictionary<string, GameObject>();
            restPos = new Vector3[bones.Length];
            restRot = new Quaternion[bones.Length];
            for (int i = 0; i < bones.Length; i++)
            {
                if (bones[i] == null) continue;
                boneMap[bones[i].name] = bones[i];
                restPos[i] = bones[i].localPosition;
                restRot[i] = bones[i].localRotation;
            }
            foreach (var s in sockets) if (s != null) socketMap[s.name.StartsWith("socket_") ? s.name.Substring(7) : s.name] = s;
            foreach (var p in pieces) if (p != null) pieceMap[p.name] = p;
        }

        public Transform Bone(string name) { Build(); return boneMap.TryGetValue(name, out var t) ? t : null; }
        public Transform Socket(string name) { Build(); return socketMap.TryGetValue(name, out var t) ? t : null; }
        public GameObject Piece(string name) { Build(); return pieceMap.TryGetValue(name, out var g) ? g : null; }
        public bool HasPiece(string name) { Build(); return pieceMap.ContainsKey(name); }
        public IEnumerable<GameObject> AllPieces { get { Build(); return pieceMap.Values; } }

        public void Show(string piece, bool on)
        {
            var g = Piece(piece);
            if (g != null && g.activeSelf != on) g.SetActive(on);
        }

        /// <summary>Rest local position of a bone (bones are imported with identity rest rotations).</summary>
        public Vector3 RestLocal(Transform bone)
        {
            Build();
            int i = System.Array.IndexOf(bones, bone);
            return i >= 0 ? restPos[i] : bone.localPosition;
        }

        public void ResetPose()
        {
            Build();
            for (int i = 0; i < bones.Length; i++)
            {
                if (bones[i] == null) continue;
                bones[i].localPosition = restPos[i];
                bones[i].localRotation = restRot[i];
                bones[i].localScale = Vector3.one;
            }
        }

        /// <summary>World-space bounds of all visible renderers.</summary>
        public Bounds VisualBounds()
        {
            var rs = GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(transform.position, Vector3.one * 0.5f);
            var b = rs[0].bounds;
            foreach (var r in rs) b.Encapsulate(r.bounds);
            return b;
        }
    }
}
