// The rules the ghost lives by. A worker acts only if the requesting player AND the ghost it works for
// are both allowed (ghost/policy.py checks both). A forbid always beats a permit. Every policy has an
// @id: the audit log records which ones decided.

// ---- talking and moving ----
@id("anyone-talks")
permit (principal, action == Action::"Say", resource);

@id("members-move-ghost")              // "follow me", "come here": anyone in a house, and the ghosts
permit (principal, action == Action::"Move", resource)
when { principal is Ghost || principal is Spirit || (principal is Player && principal has house) };

@id("members-preview")                 // a preview changes nothing real
permit (principal, action == Action::"Preview", resource)
when { principal is Ghost || (principal is Player && principal has house) };

// ---- building ----
@id("member-small-build")              // your own house's zone, or the commons, up to 2,000 blocks
permit (principal is Player, action == Action::"Build", resource)
when { context.blocks <= 2000
       && (if resource has house then principal has house && principal.house == resource.house else true) };

@id("member-big-build")                // your own house's zone, up to 20,000 blocks, with the head's yes
permit (principal is Player, action == Action::"Build", resource)
when { context.blocks <= 20000 && context.head_approved
       && resource has house && principal has house && principal.house == resource.house };

@id("cross-house")                     // another house's zone: only with that house head's yes
permit (principal is Player, action == Action::"Build", resource)
when { context.blocks <= 20000 && context.zone_head_approved && resource has house };

@id("ghost-own-zone")                  // a house ghost works in its own zone and the commons
permit (principal is Ghost, action in [Action::"Build", Action::"Demolish", Action::"Undo"], resource)
when { if resource has house then resource.house == principal.house else true };

@id("owner-builds")                    // the server owner can build anywhere
permit (principal is Player, action in [Action::"Build", Action::"Demolish", Action::"Undo"], resource)
when { principal.role == "owner" };

@id("undo-own")                        // you can take back your own builds
permit (principal is Player, action == Action::"Undo", resource)
when { context.own_build && principal has house };

@id("head-approves")                   // heads approve for their own house's zone (and the commons)
permit (principal is Player, action == Action::"ApproveBuild", resource)
when { principal.role == "owner"
       || (principal.role == "head"
           && (if resource has house then principal has house && principal.house == resource.house else true)) };

// ---- memory ----
@id("own-memory")
permit (principal, action == Action::"ReadMemory", resource)
when { principal is Player && resource.owner == principal };

// ---- never ----
@id("no-guest-builds")
forbid (principal is Player, action in [Action::"Build", Action::"Demolish", Action::"Preview"], resource)
when { principal.role == "guest" };

@id("protected")
forbid (principal, action in [Action::"Build", Action::"Demolish", Action::"Undo"], resource)
when { resource.protected }
unless { principal is Player && principal.role == "owner" };

@id("no-building-over-builds")         // never on top of a town's buildings, walls, roads or another build
forbid (principal, action == Action::"Build", resource)
when { context.overlaps_build };

@id("spirit-never-builds")
forbid (principal is Spirit, action, resource)
unless { action == Action::"Say" || action == Action::"Move" };
