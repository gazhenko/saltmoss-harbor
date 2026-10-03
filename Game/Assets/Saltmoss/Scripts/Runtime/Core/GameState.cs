using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Saltmoss
{
    [Serializable]
    public class Stack
    {
        public string id;
        public int count;
        public int day;   // day it was caught (fresh = today)
    }

    [Serializable]
    public class PotState
    {
        public float x, z;
        public float droppedAt;   // absolute game minutes
        public int zone;
        public bool tangled;
        public int colour;
    }

    [Serializable]
    public class SaveData
    {
        public int version = 1;
        public int day = 1;
        public float hour = 6.25f;
        public int money = 120;
        public List<Stack> hold = new List<Stack>();
        public List<Stack> stock = new List<Stack>();
        public List<Stack> pocket = new List<Stack>();     // treasures & junk carried by Pip
        public List<string> discovered = new List<string>();
        public List<string> donated = new List<string>();
        public List<string> upgrades = new List<string>();
        public List<string> flags = new List<string>();
        public List<PotState> pots = new List<PotState>();
        public int totalSales;
        public int customersServed;
        public int restoration;
        public int weather;          // Weather enum of today
        public int forecast;         // tomorrow
        public List<string> letters = new List<string>();  // open special orders (ids)
        public float nellSalesToday;
        public bool boatDocked = true;
        public float boatX, boatZ, boatYaw;
        public string playTime = "";
    }

    /// <summary>The save file and everything that changes it: money, hold, shop stock, collection, upgrades, flags.</summary>
    public static class GameState
    {
        public static SaveData D = new SaveData();
        public static event Action Changed;
        public static event Action<string> Toast;
        public static event Action<ItemDef, bool> Caught;   // item, first time

        public static string SavePath => Path.Combine(Application.persistentDataPath, "saltmoss_save.json");
        public static bool HasSave => File.Exists(SavePath);

        public static void New()
        {
            D = new SaveData();
            D.weather = (int)Weather.Clear;
            D.forecast = (int)Weather.Breezy;
            Changed?.Invoke();
        }

        public static void Save()
        {
            try
            {
                if (File.Exists(SavePath)) File.Copy(SavePath, SavePath + ".bak", true);
                File.WriteAllText(SavePath, JsonUtility.ToJson(D, true));
            }
            catch (Exception e) { Debug.LogWarning("[Save] " + e.Message); }
        }

        public static bool Load()
        {
            try
            {
                if (!HasSave) return false;
                D = JsonUtility.FromJson<SaveData>(File.ReadAllText(SavePath)) ?? new SaveData();
                Changed?.Invoke();
                return true;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Save] corrupt save, trying backup: " + e.Message);
                try { D = JsonUtility.FromJson<SaveData>(File.ReadAllText(SavePath + ".bak")); Changed?.Invoke(); return true; }
                catch { D = new SaveData(); return false; }
            }
        }

        public static void Notify() => Changed?.Invoke();
        public static void Say(string msg) => Toast?.Invoke(msg);

        // ---------------------------------------------------------------- flags & upgrades
        public static bool Flag(string f) => D.flags.Contains(f);
        public static void SetFlag(string f) { if (!D.flags.Contains(f)) { D.flags.Add(f); Changed?.Invoke(); } }
        public static bool Has(string upgrade) => D.upgrades.Contains(upgrade);

        public static int HoldCapacity => Has("hold_2") ? 36 : Has("hold_1") ? 24 : 14;
        public static int PotCount => Has("pots_3") ? 6 : Has("pots_2") ? 4 : Has("pots_1") ? 3 : 2;
        public static int DisplaySlots => Has("display") ? 12 : 6;

        // ---------------------------------------------------------------- money
        public static bool Spend(int amount)
        {
            if (D.money < amount) return false;
            D.money -= amount;
            Changed?.Invoke();
            return true;
        }

        public static void Earn(int amount, bool sale = true)
        {
            D.money += amount;
            if (sale) D.totalSales += amount;
            Changed?.Invoke();
        }

        // ---------------------------------------------------------------- stacks
        public static int Count(List<Stack> list)
        {
            int n = 0;
            foreach (var s in list) n += s.count;
            return n;
        }

        public static int Count(List<Stack> list, string id)
        {
            int n = 0;
            foreach (var s in list) if (s.id == id) n += s.count;
            return n;
        }

        public static void Add(List<Stack> list, string id, int n = 1, int day = -1)
        {
            if (day < 0) day = D.day;
            foreach (var s in list)
                if (s.id == id && s.day == day) { s.count += n; Changed?.Invoke(); return; }
            list.Add(new Stack { id = id, count = n, day = day });
            Changed?.Invoke();
        }

        /// <summary>Removes n (oldest first). Returns how many were fresh (caught today).</summary>
        public static int Remove(List<Stack> list, string id, int n = 1)
        {
            int fresh = 0;
            list.Sort((a, b) => a.day.CompareTo(b.day));
            for (int i = 0; i < list.Count && n > 0; i++)
            {
                var s = list[i];
                if (s.id != id) continue;
                int take = Mathf.Min(n, s.count);
                s.count -= take;
                n -= take;
                if (s.day == D.day) fresh += take;
            }
            list.RemoveAll(s => s.count <= 0);
            Changed?.Invoke();
            return fresh;
        }

        public static bool HoldFull => Count(D.hold) >= HoldCapacity;

        /// <summary>A catch lands on deck: into the hold (fish/crabs) or Pip's pocket (treasure/junk).</summary>
        public static bool Catch(ItemDef d)
        {
            if (d == null) return false;
            bool first = !D.discovered.Contains(d.id);
            if (first) D.discovered.Add(d.id);
            if (d.kind == Kind.Fish || d.kind == Kind.Crab)
            {
                if (HoldFull) { Say("The hold is full! Head home to unload."); Caught?.Invoke(d, first); return false; }
                Add(D.hold, d.id);
            }
            else Add(D.pocket, d.id);
            Caught?.Invoke(d, first);
            return true;
        }

        public static float AbsMinutes => D.day * 1440f + D.hour * 60f;
    }
}
