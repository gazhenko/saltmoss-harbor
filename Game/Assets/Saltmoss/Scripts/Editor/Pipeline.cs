using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace Saltmoss.EditorTools
{
    /// <summary>Headless content pipeline entry points (Tools/remote.sh content).</summary>
    public static class Pipeline
    {
        [MenuItem("Saltmoss/Pipeline/Build Content")]
        public static void Content()
        {
            Step("Textures", ProjectSetup.ConfigureTextures);
            Step("Materials", ProjectSetup.EnsureMaterials);
            Step("Post profile", () => ProjectSetup.EnsurePostProfile());
            Step("Banks", BankBuilder.BuildAll);
            var scenes = new List<string>();
            if (!CommandLine.Has("-skipWorld") && System.IO.File.Exists("Assets/Saltmoss/Data/town_layout.json"))
            {
                Step("World", WorldBuilder.Build);
                scenes.Add("Saltmoss");
            }
            Step("Gallery", GalleryBuilder.Build);
            scenes.Add("Gallery");
            SceneKit.SetBuildScenes(scenes.ToArray());
            AssetDatabase.SaveAssets();
            if (Application.isBatchMode) EditorApplication.Exit(0);
        }

        public static void Step(string name, System.Action a)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            try { a(); Debug.Log($"[Pipeline] {name} OK ({sw.Elapsed.TotalSeconds:0.0}s)"); }
            catch (System.Exception e)
            {
                Debug.LogError($"[Pipeline] {name} FAILED: {e}");
                if (Application.isBatchMode) EditorApplication.Exit(2);
                throw;
            }
        }
    }
}
