#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    def _action(self, action="tower_api_rest", args={}):
        """Return a new ansible action"""

        task = self._task.copy()

        for key in args.keys():
            task.args[key] = args[key]

        action = self._shared_loader_obj.action_loader.get(
            action,
            task=task,
            connection=self._connection,
            play_context=self._play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj
        )

        return action

    def _get_template_node_unified_job_template(self, node):
        """Get unified_job_template for a template node."""

        action = self._action(
                  action="tower_get_resource_id",
                  args=dict(type="job_template",
                            name=node["template_name"],
                            organization=self._spec["organization"]))
        return action.run(task_vars=self._task_vars)["id"]

    def _get_inventory_node_unified_job_template(self, node):
        """Get unified_job_template for an inventory node."""

        # Gather inventory id

        action = self._action(
                  action="tower_get_resource_id",
                  args=dict(type="inventory",
                            name=node["inventory_name"],
                            organization=self._spec["organization"]))
        inventory_id = action.run(task_vars=self._task_vars)["id"]

        # Gather inventory updates

        inventory_updates_path = "/inventory_updates/"
        action = self._action(args=dict(path=inventory_updates_path,
                                        search=node["inventory_name"]))
        inventory_updates = action.run(task_vars=self._task_vars)["json"]

        # If there are not inventory updates launch an update, else gather last
        # update info

        if len(inventory_updates) == 0:
            # Launch inventory update

            update_inventory_path = \
                "/inventories/{id}/update_inventory_sources/"\
                .format(id=inventory_id)
            action = self._action(args=dict(path=update_inventory_path,
                                            method="POST"))
            result = action.run(task_vars=self._task_vars)["json"]

            # Get launched update info

            update_path = "/inventory_updates/{id}".format(
                                    id=result[0]["inventory_update"])
            action = self._action(args=dict(path=update_path))
            inventory_update = action.run(
                                    task_vars=self._task_vars)["json"]
            unified_job_template = inventory_update["unified_job_template"]
        else:
            # Get last inventory update info

            unified_job_template = None
            for update in inventory_updates:
                if update["inventory"] == inventory_id:
                    unified_job_template = update["unified_job_template"]

        return unified_job_template

    def _get_project_node_unified_job_template(self, node):
        """Get unified_job_template for a project node."""

        action = self._action(
                  action="tower_get_resource_id",
                  args=dict(type="project",
                            name=node["project_name"],
                            organization=self._spec["organization"]))
        print()
        return action.run(task_vars=self._task_vars)["id"]

    def _complete_nodes_with_unified_job_template(self):
        """Complete nodes with unified_job_template."""

        nodes_with_unified_job_template = list()
        for node in self._spec.get("nodes", []):
            if "template_name" in node:
                node["unified_job_template"] = \
                    self._get_template_node_unified_job_template(node)
            elif "inventory_name" in node:
                node["unified_job_template"] = \
                    self._get_inventory_node_unified_job_template(node)
            elif "project_name" in node:
                node["unified_job_template"] = \
                    self._get_project_node_unified_job_template(node)

            nodes_with_unified_job_template.append(node)

        return nodes_with_unified_job_template

    def _get_nodes_by_id(self, ids, nodes):
        """Return the the nodes with the maching ids"""
        result = list()

        if len(ids) == 0:
            return result

        for node in nodes:
            if node["id"] in ids:
                result.append(node)
        return result

    def _get_real_ids(self, ids, nodes):
        """Return nodes real ids given after node creation"""

        result = list()
        for node in nodes:
            if node["id"] in ids:
                result.append(node["real_id"])

        return result

    def _to_tree(self, nodes, root_nodes=None):
        """Return nodes in a tree structure"""

        if root_nodes is None:
            # Calculate nodes that are child of another ones

            root_nodes = list()
            childs_ids = list()
            for node in nodes:
                childs_ids += node.get("always_nodes", [])
                childs_ids += node.get("failure_nodes", [])
                childs_ids += node.get("success_nodes", [])

            # Calculate root nodes

            for node in nodes:
                if node.get("id") not in childs_ids:
                    root_nodes.append(node)

        # Build tree

        tree = list()
        for node in root_nodes:
            always_nodes = self._to_tree(
                        nodes,
                        self._get_nodes_by_id(
                                        node.get("always_nodes", []), nodes))
            failure_nodes = self._to_tree(
                        nodes,
                        self._get_nodes_by_id(
                                        node.get("failure_nodes", []), nodes))
            success_nodes = self._to_tree(
                        nodes,
                        self._get_nodes_by_id(
                                        node.get("success_nodes", []), nodes))

            unified_job_template = node["unified_job_template"]

            node_tree = dict(workflow_job_template=self._spec["id"],
                             unified_job_template=unified_job_template,
                             always_nodes=always_nodes,
                             failure_nodes=failure_nodes,
                             success_nodes=success_nodes)

            tree.append(node_tree)

        return tree

    def _gather(self):
        """Gather necessary info to setup the workflow node"""

        self._spec = self._task.args["spec"]
        self._spec["nodes"] = self._complete_nodes_with_unified_job_template()
        self._new_nodes = self._to_tree(self._spec.get("nodes", []))

        # Gather current workflow nodes

        self._workflow_nodes_path = \
            "/workflow_job_templates/{id}/workflow_nodes/".format(
                id=self._spec["id"])
        action = self._action(args=dict(path=self._workflow_nodes_path))
        self._current_nodes_raw = action.run(task_vars=self._task_vars)["json"]
        self._current_nodes = self._to_tree(self._current_nodes_raw)

    def _clean(self):
        """Clean current nodes."""

        for node in self._current_nodes_raw:
            node_path = "/workflow_job_template_nodes/{id}/".format(
                                                                id=node["id"])
            action = self._action(args=dict(path=node_path,
                                            method="DELETE"))
            action.run(task_vars=self._task_vars)

    def _associate(self, node_id, partners_ids, where):
        """Associate nodes to another node."""

        for partner_id in partners_ids:
            partner_path = "/workflow_job_template_nodes/{id}/{where}/".format(
                                                    id=node_id, where=where)
            action = self._action(args=dict(path=partner_path,
                                            method="POST",
                                            fields=dict(id=partner_id)))
            action.run(task_vars=self._task_vars)

    def _setup(self):
        """Setup the workflow node"""

        self._gather()

        changed = False
        if self._current_nodes != self._new_nodes:
            self._clean()
            changed = True

            nodes = self._spec.get("nodes", [])

            # Create nodes

            for node in nodes:
                node_path = "/workflow_job_template_nodes/"
                workflow_job_template = self._spec["id"]
                unified_job_template = node["unified_job_template"]
                action = self._action(
                    args=dict(
                          path=node_path,
                          method="POST",
                          fields=dict(
                            workflow_job_template=workflow_job_template,
                            unified_job_template=unified_job_template)))
                result = action.run(task_vars=self._task_vars)
                node["real_id"] = result["json"]["id"]

            # Create node relations

            for node in nodes:
                always_nodes = self._get_real_ids(
                                        node.get("always_nodes", []), nodes)
                failure_nodes = self._get_real_ids(
                                        node.get("failure_nodes", []), nodes)
                success_nodes = self._get_real_ids(
                                        node.get("success_nodes", []), nodes)

                self._associate(node["real_id"],
                                always_nodes,
                                "always_nodes")

                self._associate(node["real_id"],
                                failure_nodes,
                                "failure_nodes")

                self._associate(node["real_id"],
                                success_nodes,
                                "success_nodes")

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars

        try:
            result = self._setup()
        except Exception:
            result = dict(failed=True, msg="Cannot manage workflows nodes")

        return result
