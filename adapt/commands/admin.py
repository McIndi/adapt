import argparse
from pathlib import Path
from typing import List

from sqlmodel import Session, select

from ..admin.resources import list_resources
from ..config import AdaptConfig
from ..storage import Permission, Group, GroupPermission, init_database, Action, get_db_session


def run_admin(args):
    """Run admin subcommands."""
    if args.admin_command == "list-resources":
        run_list_resources(Path(args.root).resolve())
    elif args.admin_command == "create-permissions":
        run_create_permissions(
            root=Path(args.root).resolve(),
            resources=args.resources,
            all_group_name=args.all_group,
            read_group_name=args.read_group
        )


def run_list_resources(root: Path) -> None:
    """List all discovered resources."""
    resources = list_resources(root)
    if not resources:
        print("No resources discovered.")
        return
    
    print("Discovered resources:")
    for resource in sorted(resources):
        print(f"  {resource}")


def run_create_permissions(root: Path, resources: List[str], all_group_name: str, read_group_name: str) -> None:
    """Create permissions and groups for the given resources."""
    if "__all__" in resources:
        all_res = list_resources(root)
        print(f"Using all {len(all_res)} resources")
    else:
        all_res = resources
    
    if not all_res:
        print("No resources to process.")
        return
    
    # Create dynamic group names based on resources
    sorted_res = sorted(all_res)
    res_suffix = "_".join(sorted_res)
    dynamic_all_group_name = f"{all_group_name}_{res_suffix}"
    dynamic_read_group_name = f"{read_group_name}_{res_suffix}"
    
    config = AdaptConfig(root=root)
    engine = init_database(config.db_path)
    
    with Session(engine) as db:
        # Create permissions
        created_perms = []
        for res in all_res:
            for action in [Action.read, Action.write]:
                # Check if exists
                existing = db.exec(select(Permission).where(
                    Permission.resource == res,
                    Permission.action == action
                )).first()
                if existing:
                    print(f"Permission {action.value} on {res} already exists")
                    created_perms.append(existing)
                else:
                    perm = Permission(resource=res, action=action, description=f"{action.value.capitalize()} access to {res}")
                    db.add(perm)
                    db.commit()
                    db.refresh(perm)
                    created_perms.append(perm)
                    print(f"Created permission {action.value} on {res}")
        
        # Create all permissions group
        all_group = db.exec(select(Group).where(Group.name == dynamic_all_group_name)).first()
        if not all_group:
            all_group = Group(name=dynamic_all_group_name, description=f"All permissions for resources: {', '.join(sorted_res)}")
            db.add(all_group)
            db.commit()
            db.refresh(all_group)
            print(f"Created group '{dynamic_all_group_name}'")
        else:
            print(f"Group '{dynamic_all_group_name}' already exists")
        
        # Assign all permissions to all_group
        for perm in created_perms:
            existing_gp = db.exec(select(GroupPermission).where(
                GroupPermission.group_id == all_group.id,
                GroupPermission.permission_id == perm.id
            )).first()
            if not existing_gp:
                gp = GroupPermission(group_id=all_group.id, permission_id=perm.id)
                db.add(gp)
                print(f"Assigned {perm.action.value} on {perm.resource} to group '{dynamic_all_group_name}'")
        
        # Create read permissions group
        read_perms = [p for p in created_perms if p.action == Action.read]
        read_group = db.exec(select(Group).where(Group.name == dynamic_read_group_name)).first()
        if not read_group:
            read_group = Group(name=dynamic_read_group_name, description=f"Read permissions for resources: {', '.join(sorted_res)}")
            db.add(read_group)
            db.commit()
            db.refresh(read_group)
            print(f"Created group '{dynamic_read_group_name}'")
        else:
            print(f"Group '{dynamic_read_group_name}' already exists")
        
        # Assign read permissions to read_group
        for perm in read_perms:
            existing_gp = db.exec(select(GroupPermission).where(
                GroupPermission.group_id == read_group.id,
                GroupPermission.permission_id == perm.id
            )).first()
            if not existing_gp:
                gp = GroupPermission(group_id=read_group.id, permission_id=perm.id)
                db.add(gp)
                print(f"Assigned {perm.action.value} on {perm.resource} to group '{dynamic_read_group_name}'")
        
        # Create individual resource groups
        for res in all_res:
            res_read_perms = [p for p in created_perms if p.resource == res and p.action == Action.read]
            res_all_perms = [p for p in created_perms if p.resource == res]
            
            # Readonly group for this resource
            readonly_group_name = f"{res}_readonly"
            readonly_group = db.exec(select(Group).where(Group.name == readonly_group_name)).first()
            if not readonly_group:
                readonly_group = Group(name=readonly_group_name, description=f"Read-only access to {res}")
                db.add(readonly_group)
                db.commit()
                db.refresh(readonly_group)
                print(f"Created group '{readonly_group_name}'")
            else:
                print(f"Group '{readonly_group_name}' already exists")
            
            for perm in res_read_perms:
                existing_gp = db.exec(select(GroupPermission).where(
                    GroupPermission.group_id == readonly_group.id,
                    GroupPermission.permission_id == perm.id
                )).first()
                if not existing_gp:
                    gp = GroupPermission(group_id=readonly_group.id, permission_id=perm.id)
                    db.add(gp)
                    print(f"Assigned {perm.action} on {perm.resource} to group '{readonly_group_name}'")
            
            # Read/write group for this resource
            readwrite_group_name = f"{res}_readwrite"
            readwrite_group = db.exec(select(Group).where(Group.name == readwrite_group_name)).first()
            if not readwrite_group:
                readwrite_group = Group(name=readwrite_group_name, description=f"Read/write access to {res}")
                db.add(readwrite_group)
                db.commit()
                db.refresh(readwrite_group)
                print(f"Created group '{readwrite_group_name}'")
            else:
                print(f"Group '{readwrite_group_name}' already exists")
            
            for perm in res_all_perms:
                existing_gp = db.exec(select(GroupPermission).where(
                    GroupPermission.group_id == readwrite_group.id,
                    GroupPermission.permission_id == perm.id
                )).first()
                if not existing_gp:
                    gp = GroupPermission(group_id=readwrite_group.id, permission_id=perm.id)
                    db.add(gp)
                    print(f"Assigned {perm.action} on {perm.resource} to group '{readwrite_group_name}'")
        
        db.commit()
        print("Permissions and groups created successfully.")