## Saltmoss Harbor v1.1.0 — charts and a coastline

<!-- easy-installers:start -->
## Easy installers — no coding tools needed

| Computer | Download | Install |
| --- | --- | --- |
| Mac, Apple Silicon or Intel | [Download Mac installer](https://github.com/gazhenko/saltmoss-harbor/releases/download/v1.1.0/SaltmossHarbor-v1.1.0-macOS-universal.dmg) | Open the disk image, drag **Saltmoss Harbor** to **Applications**, then open it from Applications. |
| Windows 10/11, Intel/AMD 64-bit | [Download Windows installer](https://github.com/gazhenko/saltmoss-harbor/releases/download/v1.1.0/SaltmossHarbor-v1.1.0-Windows-x64-Setup.exe) | Open Setup and choose **Next → Install → Finish**. Use the desktop or Start menu shortcut. |

The installers include the whole game and work offline. No agent, Unity editor or terminal is needed; Windows installation needs no administrator password. Quit the game before updating. Your saved progress is kept during updates and removal.

[Read the installation guide](https://github.com/gazhenko/saltmoss-harbor/releases/download/v1.1.0/START-HERE.txt) for first-launch approval prompts and removal instructions. [Installer checksums](https://github.com/gazhenko/saltmoss-harbor/releases/download/v1.1.0/INSTALLER-SHA256SUMS.txt) · [Packaging validation](https://github.com/gazhenko/saltmoss-harbor/releases/download/v1.1.0/installer-validation.json).

The Mac app is ad-hoc signed and not Apple-notarized; the Windows installer is unsigned. All packaged game files were checked against this release's source archives. The Windows installer has not been run on Windows hardware.
<!-- easy-installers:end -->

### What's new in 1.1.0
- **A map.** Press **M** (View on Xbox, Create on PlayStation, − on Switch) for a paper chart: the town with every roof
  and boardwalk and the places that matter, or the sea chart with the fishing grounds, your crab pots in their buoy
  colours, the Sally Mae and the old wreck. Out at sea a little chart sits in the corner with the boat in the middle.
- **A mainland behind the harbour.** From the boat the town used to look like a small island with its edges cut off,
  because only the part you walk on was built. Saltmoss now sits on a long coast that runs away east and west, with
  beaches and white surf, cliffs further along, rolling hills behind the cottages and mountains fading into the haze.
- **Smooth sailing.** Under way the Sally Mae seemed to lurch forwards and back many times a second: the camera glided
  while the boat only moved on the stop-motion frames. Now whatever the camera follows (and everything riding on it)
  travels smoothly, and only its bobbing, pitching and rolling keep the hand-animated rhythm. The trailer is re-shot.
- **Smaller prompts that fit.** With a controller the button prompts were stretched across the screen and the words
  were squeezed out of the side; the button's colour codes were being counted as letters. Prompts are now compact and
  sized to what they say, and every screen shape (ultrawide, 16:10) gets room rather than a squeeze.
- **Bunting that hangs from something.** The strings of flags across the street and the walks were all one length and
  floated in mid-air at their ends. Each string is now made to the length between its two posts, and the strings on the
  hillside have their own poles.
- **The forecast board's chalk** now fits inside the slate instead of running over the frame.

### 1.0.1 — she stays out


### What's new in 1.0.1
- **Fixed: boarding the Sally Mae kicked you straight back off.** The key press that took you aboard was also read
  as "Tie up at the berth", so a few seconds later Pip was back on the dock. Boarding now only boards, and tying up is
  offered once you've actually taken her out and brought her back.
- **Fixed: crab pots and lines inside the harbour.** Only a small circle around the harbour mouth counted as "in the
  harbour", so you could drop pots and cast right beside the pier. Now the whole basin inside the harbour arms
  counts, as the tutorial says: sail out past the mouth to fish.

### Saltmoss Harbor v1.0.0 — the first catch

A cosy claymation fishing demo. You are **Pip**, a young puffin who inherits Gran's crab boat and her shuttered fish
shop in the sea-worn town of Saltmoss Harbor. Haul crab pots, cast for fish shadows, dredge the Grey Deep for treasure,
ride out storms, serve customers at the Salty Puffin, fill Professor Inkwell's museum — and bring the harbour back to life.

**Downloads** (below): macOS universal (Apple Silicon + Intel), Windows x64, Linux x64, plus the trailer and checksums.
See the [installation guide](https://github.com/gazhenko/saltmoss-harbor/releases/download/v1.1.0/START-HERE.txt) for setup instructions. No coding tools are needed.

### In this demo
- Three fishing grounds (the Shallows, Kelp Reach, the Grey Deep) with crab pots, line fishing and treasure dredging
- 16 fish, 5 crabs, 20 treasures and 3 bits of junk, each with its own catch moment and museum lecture
- The Salty Puffin shop with queuing customers, special orders by post, upgrades for the boat and the shop
- Rogue waves, icing, rain, fog and storms — cosy drama, nothing lost for good
- Five townsfolk with live clay dialogue portraits and Animalese-style voice blips
- A three-step harbour restoration ending with the lighthouse relit
- Stop-motion on twos (or ones, or off), full-film camera mode, remappable keyboard and controller controls

Everything — models, textures, music, sounds and voices — is generated from code in this repository.
