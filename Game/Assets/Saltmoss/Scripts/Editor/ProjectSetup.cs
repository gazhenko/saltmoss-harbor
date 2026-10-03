using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Saltmoss.EditorTools
{
    /// <summary>
    /// One-shot project configuration: URP assets and renderer features, quality tiers, player settings, layers, the
    /// shared clay materials and the post-processing profile. Batch: -executeMethod Saltmoss.EditorTools.ProjectSetup.Run
    /// </summary>
    public static class ProjectSetup
    {
        public const string SettingsDir = "Assets/Saltmoss/Settings";
        public const string MaterialsDir = "Assets/Saltmoss/Materials";
        public const string TexDir = "Assets/Saltmoss/Art/Textures";
        public const string Version = "1.0.1";

        // layers
        public const int LayerPlayer = 8, LayerBoat = 9, LayerWorld = 10, LayerWater = 11, LayerInteract = 12, LayerPortrait = 13, LayerIcon = 14, LayerNPC = 15;

        [MenuItem("Saltmoss/Setup/Configure Project")]
        public static void Run()
        {
            Directory.CreateDirectory(SettingsDir);
            Directory.CreateDirectory(MaterialsDir);
            ConfigureLayers();
            ConfigurePlayer();
            ConfigureTextures();
            var high = EnsurePipeline("High", 1.0f, 110f, 4096, 4, 4);
            var med = EnsurePipeline("Medium", 0.9f, 80f, 2048, 3, 2);
            var low = EnsurePipeline("Low", 0.75f, 55f, 1024, 2, 1);
            GraphicsSettings.defaultRenderPipeline = high;
            ConfigureQuality(low, med, high);
            EnsureMaterials();
            EnsurePostProfile();
            ConfigureTime();
            ImportTmpEssentials();
            AssetDatabase.SaveAssets();
            // claymesh imports depend on the materials: refresh them now that the materials exist
            foreach (var guid in AssetDatabase.FindAssets("", new[] { "Assets/Saltmoss/Models" }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                if (p.EndsWith(".claymesh")) AssetDatabase.ImportAsset(p, ImportAssetOptions.ForceUpdate);
            }
            Debug.Log("[Saltmoss] Project configured.");
        }

        static void ConfigureLayers()
        {
            var tm = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0];
            var so = new SerializedObject(tm);
            var layers = so.FindProperty("layers");
            void Set(int i, string n) { layers.GetArrayElementAtIndex(i).stringValue = n; }
            Set(LayerPlayer, "Player"); Set(LayerBoat, "Boat"); Set(LayerWorld, "World"); Set(LayerWater, "Water");
            Set(LayerInteract, "Interact"); Set(LayerPortrait, "Portrait"); Set(LayerIcon, "Icon"); Set(LayerNPC, "NPC");
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void ConfigurePlayer()
        {
            PlayerSettings.companyName = "Gazhenko";
            PlayerSettings.productName = "Saltmoss Harbor";
            PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Standalone, "com.gazhenko.saltmoss");
            PlayerSettings.bundleVersion = Version;
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.SplashScreen.show = false;
            PlayerSettings.gpuSkinning = true;
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.SetApiCompatibilityLevel(UnityEditor.Build.NamedBuildTarget.Standalone, ApiCompatibilityLevel.NET_Standard);
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneOSX, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneOSX, new[] { GraphicsDeviceType.Metal });
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneLinux64, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneLinux64, new[] { GraphicsDeviceType.Vulkan, GraphicsDeviceType.OpenGLCore });
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[] { GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Direct3D12, GraphicsDeviceType.Vulkan });

            var ps = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0];
            var so = new SerializedObject(ps);
            var input = so.FindProperty("activeInputHandler");
            if (input != null) input.intValue = 2;   // both (Input System for gameplay)
            so.ApplyModifiedPropertiesWithoutUndo();

            var iconTex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Saltmoss/Art/Icon/icon.png");
            if (iconTex != null) PlayerSettings.SetIcons(UnityEditor.Build.NamedBuildTarget.Unknown, new[] { iconTex }, IconKind.Any);
        }

        public static void ConfigureTextures()
        {
            if (!AssetDatabase.IsValidFolder(TexDir)) return;
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { TexDir }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                if (AssetImporter.GetAtPath(p) is TextureImporter ti) TextureRules.Apply(ti, p);
                AssetDatabase.ImportAsset(p, ImportAssetOptions.ForceUpdate);
            }
        }

        static UniversalRenderPipelineAsset EnsurePipeline(string tier, float renderScale, float shadowDistance, int shadowRes, int cascades, int msaa)
        {
            string rendererPath = $"{SettingsDir}/URP_{tier}_Renderer.asset";
            string assetPath = $"{SettingsDir}/URP_{tier}.asset";
            var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(rendererPath);
            if (renderer == null)
            {
                renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(renderer, rendererPath);
            }
            renderer.postProcessData ??= AssetDatabase.LoadAssetAtPath<PostProcessData>("Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset");
            renderer.renderingMode = RenderingMode.ForwardPlus;
            renderer.depthPrimingMode = DepthPrimingMode.Disabled;
            renderer.copyDepthMode = CopyDepthMode.AfterOpaques;
            EditorUtility.SetDirty(renderer);
            if (tier != "Low") EnsureSSAO(renderer, tier == "High");

            var asset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(assetPath);
            if (asset == null)
            {
                asset = UniversalRenderPipelineAsset.Create(renderer);
                AssetDatabase.CreateAsset(asset, assetPath);
            }
            var so = new SerializedObject(asset);
            void SetF(string n, float v) { var p = so.FindProperty(n); if (p != null) p.floatValue = v; else Debug.LogWarning("URP prop missing " + n); }
            void SetI(string n, int v) { var p = so.FindProperty(n); if (p != null) p.intValue = v; else Debug.LogWarning("URP prop missing " + n); }
            void SetB(string n, bool v) { var p = so.FindProperty(n); if (p != null) p.boolValue = v; else Debug.LogWarning("URP prop missing " + n); }
            var list = so.FindProperty("m_RendererDataList");
            list.arraySize = 1;
            list.GetArrayElementAtIndex(0).objectReferenceValue = renderer;
            SetI("m_DefaultRendererIndex", 0);
            SetB("m_RequireDepthTexture", true);
            SetB("m_RequireOpaqueTexture", false);
            SetB("m_SupportsHDR", true);
            SetI("m_MSAA", msaa);
            SetF("m_RenderScale", renderScale);
            SetI("m_MainLightRenderingMode", 1);
            SetB("m_MainLightShadowsSupported", true);
            SetI("m_MainLightShadowmapResolution", shadowRes);
            SetI("m_AdditionalLightsRenderingMode", 1);
            SetI("m_AdditionalLightsPerObjectLimit", 8);
            SetB("m_AdditionalLightShadowsSupported", false);
            SetF("m_ShadowDistance", shadowDistance);
            SetI("m_ShadowCascadeCount", cascades);
            SetB("m_SoftShadowsSupported", true);
            SetI("m_ColorGradingMode", 1);
            SetI("m_ColorGradingLutSize", 32);
            SetB("m_UseSRPBatcher", true);
            SetB("m_SupportsDynamicBatching", false);
            SetB("m_SupportsLightLayers", true);   // rendering layers: dialogue portrait lamps light only the portrait studio
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(asset);
            return asset;
        }

        /// <summary>Contact shadows where clay pieces press together and under puppets' feet.</summary>
        static void EnsureSSAO(UniversalRendererData data, bool high)
        {
            ScreenSpaceAmbientOcclusion ao = null;
            foreach (var f in data.rendererFeatures) if (f is ScreenSpaceAmbientOcclusion a) ao = a;
            if (ao == null)
            {
                ao = ScriptableObject.CreateInstance<ScreenSpaceAmbientOcclusion>();
                ao.name = "ClaySSAO";
                AssetDatabase.AddObjectToAsset(ao, data);
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(ao, out _, out long localId);
                var dso = new SerializedObject(data);
                var feats = dso.FindProperty("m_RendererFeatures");
                var map = dso.FindProperty("m_RendererFeatureMap");
                feats.arraySize++;
                feats.GetArrayElementAtIndex(feats.arraySize - 1).objectReferenceValue = ao;
                map.arraySize++;
                map.GetArrayElementAtIndex(map.arraySize - 1).longValue = localId;
                dso.ApplyModifiedPropertiesWithoutUndo();
            }
            var so = new SerializedObject(ao);
            void F(string n, float v) { var p = so.FindProperty("m_Settings." + n); if (p != null) p.floatValue = v; else Debug.LogWarning("SSAO prop missing " + n); }
            void B(string n, bool v) { var p = so.FindProperty("m_Settings." + n); if (p != null) p.boolValue = v; else Debug.LogWarning("SSAO prop missing " + n); }
            void I(string n, int v) { var p = so.FindProperty("m_Settings." + n); if (p != null) p.intValue = v; else Debug.LogWarning("SSAO prop missing " + n); }
            F("Radius", 0.32f);
            F("Intensity", 1.35f);
            F("DirectLightingStrength", 0.4f);
            F("Falloff", 60f);
            B("Downsample", !high);
            B("AfterOpaque", false);
            I("Source", 1);        // depth normals
            I("NormalSamples", 1);
            so.ApplyModifiedPropertiesWithoutUndo();
            ao.SetActive(true);
            EditorUtility.SetDirty(ao);
            EditorUtility.SetDirty(data);
        }

        static void ConfigureQuality(RenderPipelineAsset low, RenderPipelineAsset med, RenderPipelineAsset high)
        {
            var qs = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/QualitySettings.asset")[0];
            var so = new SerializedObject(qs);
            var levels = so.FindProperty("m_QualitySettings");
            levels.arraySize = 3;
            string[] names = { "Low", "Medium", "High" };
            RenderPipelineAsset[] assets = { low, med, high };
            for (int i = 0; i < 3; i++)
            {
                var l = levels.GetArrayElementAtIndex(i);
                l.FindPropertyRelative("name").stringValue = names[i];
                l.FindPropertyRelative("customRenderPipeline").objectReferenceValue = assets[i];
                var vs = l.FindPropertyRelative("vSyncCount"); if (vs != null) vs.intValue = 1;
                var af = l.FindPropertyRelative("anisotropicTextures"); if (af != null) af.intValue = 2;
                var lb = l.FindPropertyRelative("lodBias"); if (lb != null) lb.floatValue = i == 2 ? 2.0f : 1.4f;
                var pl = l.FindPropertyRelative("pixelLightCount"); if (pl != null) pl.intValue = 8;
                var sb = l.FindPropertyRelative("skinWeights"); if (sb != null) sb.intValue = 4;
            }
            so.FindProperty("m_CurrentQuality").intValue = 2;
            var per = so.FindProperty("m_PerPlatformDefaultQuality");
            if (per != null)
                for (int i = 0; i < per.arraySize; i++) per.GetArrayElementAtIndex(i).FindPropertyRelative("second").intValue = 2;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static Material Mat(string name, string shader)
        {
            string path = $"{MaterialsDir}/{name}.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            var sh = Shader.Find(shader);
            if (sh == null) { Debug.LogError("[Saltmoss] missing shader " + shader); sh = Shader.Find("Universal Render Pipeline/Lit"); }
            if (m == null)
            {
                m = new Material(sh);
                AssetDatabase.CreateAsset(m, path);
            }
            else m.shader = sh;
            return m;
        }

        public static void EnsureMaterials()
        {
            var finger = AssetDatabase.LoadAssetAtPath<Texture2D>($"{TexDir}/clay_finger_n.png");
            var tool = AssetDatabase.LoadAssetAtPath<Texture2D>($"{TexDir}/clay_tool_n.png");
            var ripple = AssetDatabase.LoadAssetAtPath<Texture2D>($"{TexDir}/sea_ripple_n.png");

            var clay = Mat("Clay", "Saltmoss/Clay");
            clay.SetTexture("_FingerNormal", finger);
            clay.SetTexture("_ToolNormal", tool);
            clay.enableInstancing = true;
            EditorUtility.SetDirty(clay);

            var glow = Mat("ClayGlow", "Saltmoss/Clay");
            glow.CopyPropertiesFromMaterial(clay);
            glow.SetFloat("_Emissive", 1f);
            glow.SetFloat("_SSS", 0.2f);
            glow.SetFloat("_FingerStrength", 0.2f);
            EditorUtility.SetDirty(glow);

            var foam = Mat("ClayFoam", "Saltmoss/Clay");
            foam.CopyPropertiesFromMaterial(clay);
            foam.SetFloat("_SSS", 0.25f);
            foam.SetFloat("_MatteSmooth", 0.3f);
            EditorUtility.SetDirty(foam);

            var net = Mat("ClayNet", "Saltmoss/Clay");
            net.CopyPropertiesFromMaterial(clay);
            net.SetFloat("_Cull", (float)CullMode.Off);
            EditorUtility.SetDirty(net);

            var cotton = Mat("Cotton", "Saltmoss/Cotton");
            cotton.enableInstancing = true;
            EditorUtility.SetDirty(cotton);

            var sea = Mat("Sea", "Saltmoss/ClaySea");
            sea.SetTexture("_RippleNormal", ripple);
            sea.SetTexture("_FingerNormal", finger);
            EditorUtility.SetDirty(sea);

            var back = Mat("Backdrop", "Saltmoss/Backdrop");
            back.SetTexture("_Clouds", AssetDatabase.LoadAssetAtPath<Texture2D>($"{TexDir}/sky_clouds.png"));
            back.SetTexture("_Paper", AssetDatabase.LoadAssetAtPath<Texture2D>($"{TexDir}/paper.png"));
            EditorUtility.SetDirty(back);

            // plain (non-claymesh) clay for procedural meshes: rest position = object position
            var plain = Mat("ClayPlain", "Saltmoss/Clay");
            plain.CopyPropertiesFromMaterial(clay);
            plain.SetFloat("_RestFromUV1", 0f);
            plain.SetFloat("_VertexColor", 0f);
            EditorUtility.SetDirty(plain);
            AssetDatabase.SaveAssets();
        }

        public static VolumeProfile EnsurePostProfile()
        {
            string path = $"{SettingsDir}/ClayPost.asset";
            var prof = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
            if (prof == null)
            {
                prof = ScriptableObject.CreateInstance<VolumeProfile>();
                AssetDatabase.CreateAsset(prof, path);
            }
            T Get<T>() where T : VolumeComponent
            {
                if (!prof.TryGet<T>(out var c))
                {
                    c = prof.Add<T>(true);
                    c.name = typeof(T).Name;
                    AssetDatabase.AddObjectToAsset(c, prof);
                }
                c.active = true;
                return c;
            }
            var tone = Get<Tonemapping>(); tone.mode.Override(TonemappingMode.ACES);
            var bloom = Get<Bloom>(); bloom.intensity.Override(0.22f); bloom.threshold.Override(1.1f); bloom.scatter.Override(0.6f);
            var vig = Get<Vignette>(); vig.intensity.Override(0.26f); vig.smoothness.Override(0.45f);
            var grain = Get<FilmGrain>(); grain.type.Override(FilmGrainLookup.Medium2); grain.intensity.Override(0.22f); grain.response.Override(0.7f);
            var ca = Get<ColorAdjustments>(); ca.contrast.Override(10f); ca.saturation.Override(4f); ca.postExposure.Override(0.15f);
            var wb = Get<WhiteBalance>(); wb.temperature.Override(6f); wb.tint.Override(2f);
            var smh = Get<ShadowsMidtonesHighlights>();
            smh.shadows.Override(new Vector4(0.96f, 0.98f, 1.06f, 0f));
            smh.highlights.Override(new Vector4(1.04f, 1.01f, 0.96f, 0f));
            var dof = Get<DepthOfField>();
            dof.mode.Override(DepthOfFieldMode.Bokeh);
            dof.focusDistance.Override(8f);
            dof.focalLength.Override(85f);
            dof.aperture.Override(3.2f);
            dof.bladeCount.Override(6);
            var chrom = Get<ChromaticAberration>(); chrom.intensity.Override(0.06f);
            EditorUtility.SetDirty(prof);
            AssetDatabase.SaveAssets();
            return prof;
        }

        static void ConfigureTime()
        {
            var tm = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TimeManager.asset")[0];
            var so = new SerializedObject(tm);
            var cnt = so.FindProperty("Fixed Timestep.m_Count");
            if (cnt != null)
            {
                var num = so.FindProperty("Fixed Timestep.m_Rate.m_Numerator"); var den = so.FindProperty("Fixed Timestep.m_Rate.m_Denominator");
                double rate = num != null && den != null && den.longValue > 0 ? num.longValue / (double)den.longValue : 141120000.0;
                cnt.longValue = (long)System.Math.Round(rate / 60.0);
            }
            else so.FindProperty("Fixed Timestep").floatValue = 1f / 60f;
            var mx = so.FindProperty("Maximum Allowed Timestep"); if (mx != null) mx.floatValue = 0.1f;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void ImportTmpEssentials()
        {
            if (AssetDatabase.FindAssets("t:TMP_Settings").Length > 0) return;
            string[] candidates =
            {
                "Packages/com.unity.ugui/Package Resources/TMP Essential Resources.unitypackage",
                "Packages/com.unity.textmeshpro/Package Resources/TMP Essential Resources.unitypackage",
            };
            foreach (var c in candidates)
            {
                string full = Path.GetFullPath(c);
                if (File.Exists(full)) { AssetDatabase.ImportPackage(full, false); Debug.Log("[Saltmoss] Imported TMP essentials"); return; }
            }
            Debug.LogWarning("[Saltmoss] TMP essentials package not found");
        }
    }

    /// <summary>Import rules for generated art: *_n.png normal maps, the painted backdrop, paper and UI sprites.</summary>
    public class TextureRules : AssetPostprocessor
    {
        void OnPreprocessTexture()
        {
            if (!assetPath.StartsWith("Assets/Saltmoss/Art")) return;
            Apply((TextureImporter)assetImporter, assetPath);
        }

        public static void Apply(TextureImporter ti, string path)
        {
            string file = Path.GetFileNameWithoutExtension(path);
            ti.mipmapEnabled = true;
            ti.anisoLevel = 4;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
            if (file.EndsWith("_n"))
            {
                ti.textureType = TextureImporterType.NormalMap;
                ti.wrapMode = TextureWrapMode.Repeat;
                ti.sRGBTexture = false;
            }
            else if (file == "sky_clouds")
            {
                ti.textureType = TextureImporterType.Default;
                ti.wrapModeU = TextureWrapMode.Repeat;
                ti.wrapModeV = TextureWrapMode.Clamp;
                ti.alphaIsTransparency = true;
            }
            else if (file == "paper")
            {
                ti.textureType = TextureImporterType.Default;
                ti.sRGBTexture = false;
                ti.wrapMode = TextureWrapMode.Repeat;
            }
            else if (path.Contains("/UI/"))
            {
                ti.textureType = TextureImporterType.Sprite;
                ti.spriteImportMode = SpriteImportMode.Single;
                ti.mipmapEnabled = false;
                ti.alphaIsTransparency = true;
                ti.textureCompression = TextureImporterCompression.Uncompressed;
            }
        }
    }
}
