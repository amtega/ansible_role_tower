#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError
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

    def _gather(self):
        """Gather necessary info to setup the role"""

        self._spec = self._task.args["spec"]

        # Determine if we are dealing with an user o team role

        if len(self._spec.get("user", "")) > 0:
            associated_object_name = self._spec["user"]
            associated_object_type = "user"
        elif len(self._spec.get("team", "")) > 0:
            associated_object_name = self._spec["team"]
            associated_object_type = "team"
        else:
            raise AnsibleError(
                "Role spec must have defined user or team attribute")

        # Gather target object organization and role path

        target_path = \
            "/{target_type}s/{target_id}/".format(
                target_type=self._spec["target_type"],
                target_id=self._spec["target_id"])
        action = self._action(args=dict(path=target_path))
        target = action.run(task_vars=self._task_vars)["json"]

        if "organization" in target:
            target_organization = target["organization"]
        elif "summary_fields" in target:
            summary_fields = target["summary_fields"]
            if "organization" in summary_fields:
                target_organization = summary_fields["organization"]["id"]
            elif "inventory" in summary_fields:
                target_organization = \
                    summary_fields["inventory"]["organization_id"]

        target_roles = target["summary_fields"]["object_roles"]
        target_role_key = self._spec["role"].lower() + "_role"
        role_path = "/roles/{id}/".format(
                                    id=target_roles[target_role_key]["id"])

        # Gather role associated objects

        self._role_associated_objects_path = \
            "{role_path}{role_type}s/".format(role_path=role_path,
                                              role_type=associated_object_type)
        action = self._action(
                            args=dict(path=self._role_associated_objects_path,
                                      search=associated_object_name))
        self._role_associated_objects = action.run(
                                            task_vars=self._task_vars)["json"]

        associated_object_search_path = \
            "/{associated_object_type}s/".format(
                                associated_object_type=associated_object_type)
        action = self._action(
                    args=dict(path=associated_object_search_path,
                              search=associated_object_name))
        search_result = action.run(task_vars=self._task_vars)["json"]

        associated_object_id = None
        for object in search_result:
            if object["organization"] == target_organization \
               and object["name"] == associated_object_name:
                associated_object_id = object["id"]

        if associated_object_id is not None:
            self._associated_object_id = associated_object_id
        else:
            raise AnsibleError(
                "Cannot find {associated_object_type} "
                "with name {associated_object_name}"
                .format(associated_object_type=associated_object_type,
                        associated_object_name=associated_object_name))

    def _setup(self):
        """Setup the role"""

        self._gather()

        associated_object_present = False
        for associated_object in self._role_associated_objects:
            if associated_object["id"] == self._associated_object_id:
                associated_object_present = True
                break

        changed = False
        state = self._spec.get("state", "present")
        if state == "present" and not associated_object_present \
           or state == "absent" and associated_object_present:

            fields = dict(id=self._associated_object_id)

            if state == "absent":
                fields["disassociate"] = True

            action = self._action(
                            args=dict(path=self._role_associated_objects_path,
                                      method="POST",
                                      fields=fields))
            result = action.run(task_vars=self._task_vars)

            if result["status"] not in [200, 204]:
                raise AnsibleError("Failed to update role")

            changed = True

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars
        return self._setup()
