using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;
using UnityEngine.Rendering;

namespace Saltmoss.EditorTools
{
    /// <summary>
    /// Imports .claymesh files written by Tools/clay (Docs/DESIGN.md §5.2) as model prefabs: a bone hierarchy (identity
    /// rest rotations), skinned pieces (SkinnedMeshRenderer), rigid pieces parented to their bone, hidden replacement
    /// pieces (expressions, accessories) left inactive, sockets as empty children, and a <see cref="ClayModel"/> on the
    /// root. UV1 carries rest-pose model-space positions for the clay shader's triplanar detail and boil.
    /// </summary>
    [ScriptedImporter(4, "claymesh")]
    public class ClayMeshImporter : ScriptedImporter
    {
        public const string MaterialsDir = "Assets/Saltmoss/Materials";
        static readonly string[] MatNames = { "Clay", "ClayGlow", "Cotton", "ClayFoam", "ClayNet" };

        public bool castShadows = true;
        public bool addColliders;

        public override void OnImportAsset(AssetImportContext ctx)
        {
            var bytes = File.ReadAllBytes(ctx.assetPath);
            using var br = new BinaryReader(new MemoryStream(bytes));
            if (Encoding.ASCII.GetString(br.ReadBytes(4)) != "CLAY") { ctx.LogImportError("not a claymesh"); return; }
            uint version = br.ReadUInt32();
            if (version != 2) { ctx.LogImportError($"unsupported claymesh version {version}"); return; }

            string name = Path.GetFileNameWithoutExtension(ctx.assetPath);
            var root = new GameObject(name);
            var model = root.AddComponent<ClayModel>();

            // bones
            int nb = (int)br.ReadUInt32();
            var bones = new Transform[nb];
            var restPos = new Vector3[nb];
            var parents = new int[nb];
            for (int i = 0; i < nb; i++)
            {
                string bn = ReadStr(br);
                parents[i] = br.ReadInt32();
                restPos[i] = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
                bones[i] = new GameObject(bn).transform;
            }
            for (int i = 0; i < nb; i++)
            {
                var parent = parents[i] >= 0 ? bones[parents[i]] : root.transform;
                Vector3 parentPos = parents[i] >= 0 ? restPos[parents[i]] : Vector3.zero;
                bones[i].SetParent(parent, false);
                bones[i].localPosition = restPos[i] - parentPos;
                bones[i].localRotation = Quaternion.identity;
            }

            var mats = new Material[MatNames.Length];
            for (int m = 0; m < MatNames.Length; m++)
            {
                string mp = $"{MaterialsDir}/{MatNames[m]}.mat";
                ctx.DependsOnSourceAsset(mp);
                mats[m] = AssetDatabase.LoadAssetAtPath<Material>(mp);
            }

            int np = (int)br.ReadUInt32();
            var pieceObjs = new List<GameObject>();
            for (int p = 0; p < np; p++)
            {
                string pn = ReadStr(br);
                byte matClass = br.ReadByte();
                byte flags = br.ReadByte();
                int rigidBone = br.ReadInt32();
                int vc = (int)br.ReadUInt32();
                int ic = (int)br.ReadUInt32();
                var pos = new Vector3[vc];
                var nrm = new Vector3[vc];
                var col = new Color32[vc];
                for (int v = 0; v < vc; v++) pos[v] = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
                for (int v = 0; v < vc; v++) nrm[v] = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
                for (int v = 0; v < vc; v++) col[v] = new Color32(br.ReadByte(), br.ReadByte(), br.ReadByte(), br.ReadByte());
                bool skinned = (flags & 2) != 0;
                BoneWeight[] bw = null;
                if (skinned)
                {
                    var bi = new byte[vc * 4];
                    for (int k = 0; k < vc * 4; k++) bi[k] = br.ReadByte();
                    var w = new float[vc * 4];
                    for (int k = 0; k < vc * 4; k++) w[k] = br.ReadSingle();
                    bw = new BoneWeight[vc];
                    for (int v = 0; v < vc; v++)
                        bw[v] = new BoneWeight
                        {
                            boneIndex0 = bi[v * 4], weight0 = w[v * 4],
                            boneIndex1 = bi[v * 4 + 1], weight1 = w[v * 4 + 1],
                            boneIndex2 = bi[v * 4 + 2], weight2 = w[v * 4 + 2],
                            boneIndex3 = bi[v * 4 + 3], weight3 = w[v * 4 + 3],
                        };
                }
                var idx = new int[ic];
                for (int k = 0; k < ic; k++) idx[k] = (int)br.ReadUInt32();

                var rest = new List<Vector3>(pos);
                Vector3 off = !skinned && rigidBone >= 0 ? restPos[rigidBone] : Vector3.zero;
                if (off != Vector3.zero) for (int v = 0; v < vc; v++) pos[v] -= off;

                var mesh = new Mesh { name = $"{name}_{pn}" };
                mesh.indexFormat = vc > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16;
                mesh.vertices = pos;
                mesh.normals = nrm;
                mesh.colors32 = col;
                mesh.SetUVs(1, rest);
                mesh.SetTriangles(idx, 0, true);
                if (skinned)
                {
                    mesh.boneWeights = bw;
                    var bind = new Matrix4x4[nb];
                    for (int i = 0; i < nb; i++) bind[i] = Matrix4x4.Translate(-restPos[i]);
                    mesh.bindposes = bind;
                }
                mesh.RecalculateBounds();
                mesh.UploadMeshData(false);
                ctx.AddObjectToAsset("mesh_" + pn + "_" + p, mesh);

                var go = new GameObject(pn);
                Material mat = matClass < mats.Length ? mats[matClass] : mats[0];
                if (mat == null) mat = mats[0];
                if (skinned)
                {
                    go.transform.SetParent(root.transform, false);
                    var smr = go.AddComponent<SkinnedMeshRenderer>();
                    smr.sharedMesh = mesh;
                    smr.bones = bones;
                    smr.rootBone = nb > 0 ? bones[0] : null;
                    var b = mesh.bounds;
                    b.Expand(b.size.magnitude * 0.4f + 0.1f);
                    smr.localBounds = b;
                    smr.sharedMaterial = mat;
                    smr.shadowCastingMode = castShadows && matClass != 1 ? ShadowCastingMode.On : ShadowCastingMode.Off;
                    smr.quality = SkinQuality.Bone4;
                }
                else
                {
                    go.transform.SetParent(rigidBone >= 0 ? bones[rigidBone] : root.transform, false);
                    go.AddComponent<MeshFilter>().sharedMesh = mesh;
                    var mr = go.AddComponent<MeshRenderer>();
                    mr.sharedMaterial = mat;
                    mr.shadowCastingMode = castShadows && matClass != 1 ? ShadowCastingMode.On : ShadowCastingMode.Off;
                    if (addColliders && matClass == 0) go.AddComponent<MeshCollider>().sharedMesh = mesh;
                }
                if ((flags & 1) != 0) go.SetActive(false);
                pieceObjs.Add(go);
            }

            int ns = (int)br.ReadUInt32();
            var socks = new List<Transform>();
            for (int s = 0; s < ns; s++)
            {
                string sn = ReadStr(br);
                int bi = br.ReadInt32();
                var sp = new Vector3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
                var q = new Quaternion(br.ReadSingle(), br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
                var t = new GameObject("socket_" + sn).transform;
                t.SetParent(bi >= 0 ? bones[bi] : root.transform, false);
                t.localPosition = sp - (bi >= 0 ? restPos[bi] : Vector3.zero);
                t.localRotation = q;
                socks.Add(t);
            }

            model.bones = bones;
            model.pieces = pieceObjs.ToArray();
            model.sockets = socks.ToArray();
            ctx.AddObjectToAsset("root", root);
            ctx.SetMainObject(root);
        }

        static string ReadStr(BinaryReader br)
        {
            int n = br.ReadUInt16();
            return Encoding.UTF8.GetString(br.ReadBytes(n));
        }
    }
}
