from pathlib import Path
from typing import List
import logging

from ...admin.resources import list_resources
from ...config import AdaptConfig
from ...storage import Permission, Group, GroupPermission, init_database, Action, get_db_session
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


def run_create_permissions(root: Path, resources: List[str], all_group_name: str, read_group_name: str) -> None:
    """Create permissions and groups for the given resources."""
    if "__all__" in resources:
        all_res = list_resources(root)
        logger.info("Using all %d resources", len(all_res))
        print(f"Using all {len(all_res)} resources")
    else:
        all_res = resources
    
    if not all_res:
        logger.warning("No resources to process")
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
                    logger.debug("Permission %s on %s already exists", action.value, res)
                    print(f"Permission {action.value} on {res} already exists")
                    created_perms.append(existing)
                else:
                    perm = Permission(resource=res, action=action, description=f"{action.value.capitalize()} access to {res}")
                    db.add(perm)
                    db.commit()
                    db.refresh(perm)
                    created_perms.append(perm)
                    logger.info("Created permission %s on %s", action.value, res)
                    print(f"Created permission {action.value} on {res}")
        
        # Create all permissions group
        all_group = db.exec(select(Group).where(Group.name == dynamic_all_group_name)).first()
        if not all_group:
            all_group = Group(name=dynamic_all_group_name, description=f"All permissions for resources: {', '.join(sorted_res)}")
            db.add(all_group)
            db.commit()
            db.refresh(all_group)
            logger.info("Created group '%s'", dynamic_all_group_name)
            print(f"Created group '{dynamic_all_group_name}'")
        else:
            logger.debug("Group '%s' already exists", dynamic_all_group_name)
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
                logger.debug("Assigned %s on %s to group '%s'", perm.action.value, perm.resource, dynamic_all_group_name)
                print(f"Assigned {perm.action.value} on {perm.resource} to group '{dynamic_all_group_name}'")
        
        # Create read permissions group
        read_perms = [p for p in created_perms if p.action == Action.read]
        read_group = db.exec(select(Group).where(Group.name == dynamic_read_group_name)).first()
        if not read_group:
            read_group = Group(name=dynamic_read_group_name, description=f"Read permissions for resources: {', '.join(sorted_res)}")
            db.add(read_group)
            db.commit()
            db.refresh(read_group)
            logger.info("Created group '%s'", dynamic_read_group_name)
            print(f"Created group '{dynamic_read_group_name}'")
        else:
            logger.debug("Group '%s' already exists", dynamic_read_group_name)
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
                logger.debug("Assigned %s on %s to group '%s'", perm.action.value, perm.resource, dynamic_read_group_name)
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
                logger.info("Created group '%s'", readonly_group_name)
                print(f"Created group '{readonly_group_name}'")
            else:
                logger.debug("Group '%s' already exists", readonly_group_name)
                print(f"Group '{readonly_group_name}' already exists")
            
            for perm in res_read_perms:
                existing_gp = db.exec(select(GroupPermission).where(
                    GroupPermission.group_id == readonly_group.id,
                    GroupPermission.permission_id == perm.id
                )).first()
                if not existing_gp:
                    gp = GroupPermission(group_id=readonly_group.id, permission_id=perm.id)
                    db.add(gp)
                    logger.debug("Assigned %s on %s to group '%s'", perm.action, perm.resource, readonly_group_name)
                    print(f"Assigned {perm.action} on {perm.resource} to group '{readonly_group_name}'")
            
            # Read/write group for this resource
            readwrite_group_name = f"{res}_readwrite"
            readwrite_group = db.exec(select(Group).where(Group.name == readwrite_group_name)).first()
            if not readwrite_group:
                readwrite_group = Group(name=readwrite_group_name, description=f"Read/write access to {res}")
                db.add(readwrite_group)
                db.commit()
                db.refresh(readwrite_group)
                logger.info("Created group '%s'", readwrite_group_name)
                print(f"Created group '{readwrite_group_name}'")
            else:
                logger.debug("Group '%s' already exists", readwrite_group_name)
                print(f"Group '{readwrite_group_name}' already exists")
            
            for perm in res_all_perms:
                existing_gp = db.exec(select(GroupPermission).where(
                    GroupPermission.group_id == readwrite_group.id,
                    GroupPermission.permission_id == perm.id
                )).first()
                if not existing_gp:
                    gp = GroupPermission(group_id=readwrite_group.id, permission_id=perm.id)
                    db.add(gp)
                    logger.debug("Assigned %s on %s to group '%s'", perm.action, perm.resource, readwrite_group_name)
                    print(f"Assigned {perm.action} on {perm.resource} to group '{readwrite_group_name}'")
        
        db.commit()
        logger.info("Permissions and groups created successfully for %d resources", len(all_res))
        print("Permissions and groups created successfully.")