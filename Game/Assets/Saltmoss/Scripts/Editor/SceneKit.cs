using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace Saltmoss.EditorTools
{
    /// <summary>Shared pieces every generated scene needs: lamps, lens, volume, sea, backdrop.</summary>
    public static class SceneKit
    {
        public const string ScenesDir = "Assets/Saltmoss/Scenes";
        public const string ModelsDir = "Assets/Saltmoss/Models";

        public static Scene NewScene(string name)
        {
            Directory.CreateDirectory(ScenesDir);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            scene.name = name;
            return scene;
        }

        public static void Save(Scene scene)
        {
            string path = $"{ScenesDir}/{scene.name}.unity";
            EditorSceneManager.SaveScene(scene, path);
            Debug.Log($"[Saltmoss] saved {path}");
        }

        public static Material Mat(string name) => AssetDatabase.LoadAssetAtPath<Material>($"{ProjectSetup.MaterialsDir}/{name}.mat");

        public static GameObject Model(string id)
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>($"{ModelsDir}/{id}.claymesh");
            if (go == null) Debug.LogWarning($"[Saltmoss] model missing: {id}");
            return go;
        }

        public static GameObject Place(string id, Vector3 pos, float yaw = 0f, Transform parent = null, float scale = 1f)
        {
            var prefab = Model(id);
            if (prefab == null) return null;
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            go.transform.localScale = Vector3.one * scale;
            return go;
        }

        public static IEnumerable<string> ModelIds(string group)
        {
            string dir = $"{ModelsDir}/{group}";
            if (!AssetDatabase.IsValidFolder(dir)) yield break;
            foreach (var f in Directory.GetFiles(dir, "*.claymesh").OrderBy(x => x))
                yield return $"{group}/{Path.GetFileNameWithoutExtension(f)}";
        }

        public static DayCycle Lighting(float hour)
        {
            var sunGo = new GameObject("Sun");
            var sun = sunGo.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.shadows = LightShadows.Soft;
            sun.shadowBias = 0.04f;
            sun.shadowNormalBias = 0.35f;
            sun.shadowStrength = 0.85f;
            sun.renderingLayerMask = 1;   // the world only (portraits have their own studio lamps)
            var sunData = sunGo.AddComponent<UniversalAdditionalLightData>();
            sunData.softShadowQuality = SoftShadowQuality.High;
            var rimGo = new GameObject("RimLamp");
            var rim = rimGo.AddComponent<Light>();
            rim.type = LightType.Directional;
            rim.shadows = LightShadows.None;
            rim.renderingLayerMask = 1;
            var dcGo = new GameObject("DayCycle");
            var dc = dcGo.AddComponent<DayCycle>();
            dc.sun = sun;
            dc.rim = rim;
            dc.hour = hour;
            RenderSettings.sun = sun;
            dc.Apply();
            return dc;
        }

        public static Volume PostVolume()
        {
            var go = new GameObject("ClayPost");
            var v = go.AddComponent<Volume>();
            v.isGlobal = true;
            v.priority = 1;
            v.sharedProfile = ProjectSetup.EnsurePostProfile();
            return v;
        }

        public static Camera MainCamera(Vector3 pos, Vector3 lookAt, float fov = 34f)
        {
            var go = new GameObject("Main Camera");
            go.tag = "MainCamera";
            var cam = go.AddComponent<Camera>();
            cam.fieldOfView = fov;
            cam.nearClipPlane = 0.08f;
            cam.farClipPlane = 3600f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.6f, 0.7f, 0.8f);
            go.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(lookAt - pos));
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            data.antialiasing = AntialiasingMode.None;
            data.requiresDepthTexture = true;
            data.renderShadows = true;
            go.AddComponent<AudioListener>();
            go.AddComponent<ClayLens>();
            return cam;
        }

        public static SeaState Sea()
        {
            var go = new GameObject("Sea");
            go.layer = ProjectSetup.LayerWater;
            var s = go.AddComponent<SeaState>();
            s.seaMaterial = Mat("Sea");
            return s;
        }

        public static void Backdrop()
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = "Backdrop";
            Object.DestroyImmediate(go.GetComponent<Collider>());
            var mr = go.GetComponent<MeshRenderer>();
            mr.sharedMaterial = Mat("Backdrop");
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;
            go.AddComponent<Backdrop>();
        }

        /// <summary>A plain clay slab (tabletop, pedestals) using the object-space clay material.</summary>
        public static GameObject Slab(string name, Vector3 pos, Vector3 size, Color color, Transform parent = null)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = pos;
            go.transform.localScale = size;
            var mat = new Material(Mat("ClayPlain")) { name = name + "_mat" };
            mat.SetColor("_BaseColor", color);
            Directory.CreateDirectory("Assets/Saltmoss/Generated");
            AssetDatabase.CreateAsset(mat, $"Assets/Saltmoss/Generated/{name}_mat.mat");
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            go.layer = ProjectSetup.LayerWorld;
            return go;
        }

        public static void SetBuildScenes(params string[] names)
        {
            EditorBuildSettings.scenes = names.Select(n => new EditorBuildSettingsScene($"{ScenesDir}/{n}.unity", true)).ToArray();
        }
    }
}
