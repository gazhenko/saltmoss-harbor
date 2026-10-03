using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace Saltmoss.EditorTools
{
    /// <summary>
    /// Builds the Resources banks the runtime loads by name: ModelBank (every .claymesh), AudioBank (every clip),
    /// UIBank (clay sprites with their 9-slice borders + TMP fonts), and a few shared runtime materials.
    /// </summary>
    public static class BankBuilder
    {
        public const string ResDir = "Assets/Saltmoss/Resources";

        public static void BuildAll()
        {
            Directory.CreateDirectory(ResDir);
            Models();
            Audio();
            UI();
            Materials();
            AssetDatabase.SaveAssets();
        }

        static T Ensure<T>(string path) where T : ScriptableObject
        {
            var a = AssetDatabase.LoadAssetAtPath<T>(path);
            if (a == null)
            {
                a = ScriptableObject.CreateInstance<T>();
                AssetDatabase.CreateAsset(a, path);
            }
            return a;
        }

        static void Models()
        {
            var bank = Ensure<ModelBank>($"{ResDir}/ModelBank.asset");
            var ids = new List<string>();
            var prefabs = new List<GameObject>();
            foreach (var guid in AssetDatabase.FindAssets("", new[] { "Assets/Saltmoss/Models" }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                if (!p.EndsWith(".claymesh")) continue;
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(p);
                if (go == null) continue;
                string id = p.Substring("Assets/Saltmoss/Models/".Length).Replace(".claymesh", "");
                ids.Add(id);
                prefabs.Add(go);
            }
            bank.ids = ids.ToArray();
            bank.prefabs = prefabs.ToArray();
            EditorUtility.SetDirty(bank);
            Debug.Log($"[Saltmoss] ModelBank: {ids.Count} models");
        }

        static void Audio()
        {
            var bank = Ensure<AudioBank>($"{ResDir}/AudioBank.asset");
            var clips = new List<AudioClip>();
            foreach (var guid in AssetDatabase.FindAssets("t:AudioClip", new[] { "Assets/Saltmoss/Audio" }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                // music and ambiences stream; short effects decompress on load
                if (AssetImporter.GetAtPath(p) is AudioImporter ai)
                {
                    bool longClip = p.Contains("/Music/") || Path.GetFileName(p).StartsWith("amb_");
                    var s = ai.defaultSampleSettings;
                    var want = longClip ? AudioClipLoadType.Streaming : AudioClipLoadType.DecompressOnLoad;
                    if (s.loadType != want)
                    {
                        s.loadType = want;
                        s.compressionFormat = longClip ? AudioCompressionFormat.Vorbis : AudioCompressionFormat.ADPCM;
                        s.quality = 0.7f;
                        ai.defaultSampleSettings = s;
                        ai.SaveAndReimport();
                    }
                }
                var c = AssetDatabase.LoadAssetAtPath<AudioClip>(p);
                if (c != null) clips.Add(c);
            }
            bank.clips = clips.ToArray();
            EditorUtility.SetDirty(bank);
            Debug.Log($"[Saltmoss] AudioBank: {clips.Count} clips");
        }

        [System.Serializable] class Borders { }

        static void UI()
        {
            var bank = Ensure<UIBank>($"{ResDir}/UIBank.asset");
            string dir = "Assets/Saltmoss/Art/UI";
            var borders = new Dictionary<string, int>();
            string json = Path.Combine(Application.dataPath, "Saltmoss/Art/UI/ui_sprites.json");
            if (File.Exists(json))
                foreach (var line in File.ReadAllLines(json))
                {
                    var l = line.Trim().TrimEnd(',');
                    int c = l.IndexOf(':');
                    if (c < 0 || !l.StartsWith("\"")) continue;
                    borders[l.Substring(1, c - 2)] = int.Parse(l.Substring(c + 1).Trim());
                }
            var sprites = new List<Sprite>();
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { dir }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                var name = Path.GetFileNameWithoutExtension(p);
                if (AssetImporter.GetAtPath(p) is TextureImporter ti)
                {
                    int b = borders.TryGetValue(name, out var v) ? v : 0;
                    ti.GetSourceTextureWidthAndHeight(out int tw, out int th);
                    b = Mathf.Min(b, Mathf.Min(tw, th) / 2 - 2);   // a 9-slice border must leave a centre
                    var want = new Vector4(b, b, b, b);
                    if (ti.textureType != TextureImporterType.Sprite || ti.spriteImportMode != SpriteImportMode.Single || ti.spriteBorder != want)
                    {
                        ti.textureType = TextureImporterType.Sprite;
                        ti.spriteImportMode = SpriteImportMode.Single;
                        ti.spriteBorder = want;
                        ti.mipmapEnabled = false;
                        ti.alphaIsTransparency = true;
                        ti.SaveAndReimport();
                    }
                }
            }
            AssetDatabase.Refresh();
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { dir }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                var s = AssetDatabase.LoadAssetAtPath<Sprite>(p);
                if (s != null) sprites.Add(s);
                else Debug.LogWarning("[Saltmoss] not a sprite: " + p);
            }
            bank.sprites = sprites.ToArray();
            bank.display = Font("LilitaOne-Regular");
            bank.body = Font("Mali-SemiBold");
            EditorUtility.SetDirty(bank);
            Debug.Log($"[Saltmoss] UIBank: {sprites.Count} sprites, fonts {(bank.display != null)}/{(bank.body != null)}");
        }

        static TMP_FontAsset Font(string file)
        {
            string path = $"{ResDir}/{file} SDF.asset";
            var fa = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(path);
            if (fa != null) return fa;
            var font = AssetDatabase.LoadAssetAtPath<Font>($"Assets/Saltmoss/Art/Fonts/{file}.ttf");
            if (font == null) { Debug.LogWarning("[Saltmoss] missing font " + file); return null; }
            fa = TMP_FontAsset.CreateFontAsset(font, 90, 9, GlyphRenderMode.SDFAA, 2048, 2048, AtlasPopulationMode.Dynamic, true);
            fa.name = file + " SDF";
            AssetDatabase.CreateAsset(fa, path);
            fa.atlasTextures[0].name = file + " Atlas";
            AssetDatabase.AddObjectToAsset(fa.atlasTextures[0], fa);
            fa.material.name = file + " Material";
            AssetDatabase.AddObjectToAsset(fa.material, fa);
            // pre-populate the printable ASCII + a few symbols so builds don't need to rasterise on first use
            fa.TryAddCharacters(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~…—–·×♥’‘“”", out _);
            EditorUtility.SetDirty(fa);
            return fa;
        }

        static void Materials()
        {
            var cotton = AssetDatabase.LoadAssetAtPath<Material>("Assets/Saltmoss/Materials/Cotton.mat");
            if (cotton != null && AssetDatabase.LoadAssetAtPath<Material>($"{ResDir}/Cotton.mat") == null)
                AssetDatabase.CopyAsset("Assets/Saltmoss/Materials/Cotton.mat", $"{ResDir}/Cotton.mat");
            var shadow = AssetDatabase.LoadAssetAtPath<Material>($"{ResDir}/FishShadow.mat");
            if (shadow == null)
            {
                shadow = new Material(Shader.Find("Saltmoss/ShadowBlob"));
                AssetDatabase.CreateAsset(shadow, $"{ResDir}/FishShadow.mat");
            }
            if (AssetDatabase.LoadAssetAtPath<Material>($"{ResDir}/Rain.mat") == null)
                AssetDatabase.CreateAsset(new Material(Shader.Find("Saltmoss/Rain")), $"{ResDir}/Rain.mat");
            var ice = AssetDatabase.LoadAssetAtPath<Material>($"{ResDir}/Ice.mat");
            if (ice == null)
            {
                ice = new Material(AssetDatabase.LoadAssetAtPath<Material>("Assets/Saltmoss/Materials/ClayPlain.mat"));
                AssetDatabase.CreateAsset(ice, $"{ResDir}/Ice.mat");
            }
            ice.SetColor("_BaseColor", new Color(0.82f, 0.92f, 1f));
            ice.SetFloat("_Gloss", 0.85f);
            ice.SetFloat("_SSSColor", 0f);
            ice.SetColor("_SSSColor", new Color(0.5f, 0.75f, 1f));
            EditorUtility.SetDirty(ice);
        }
    }
}
