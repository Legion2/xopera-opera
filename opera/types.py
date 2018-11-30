from __future__ import print_function, unicode_literals

import collections

from opera import ansible


def get_indent(n):
    return "  " * n

class MissingImplementation(Exception):
    pass


class BadType(Exception):
    pass


class MergeError(Exception):
    pass


class Pass(object):
    # TODO(@tadeboro): Remove when we have enough classes implemented.
    def __init__(self, data):
        self._data = data

    def __str__(self):
        return str(self._data)


class String(object):
    def __init__(self, data):
        if not isinstance(data, str):
            raise BadType("String constructor takes string as input data")
        self._data = data

    def __str__(self):
        return self._data

    def __eq__(self, other):
        return self._data == other._data

    def __ne__(self, other):
        self._data != other._data


class Function(object):
    VALID_NAMES = (
        "concat",
        "get_artifact",
        "get_attribute",
        "get_input",
        "get_nodes_of_type",
        "get_operation_output",
        "get_property",
        "join",
        "token",
    )

    def __init__(self, data):
        if not isinstance(data, dict):
            raise BadType("Function constructor takes dict as input data")
        if len(data) != 1:
            raise BadType("Function constructor takes single member dict")

        (name, args), = data.items()
        if name not in self.VALID_NAMES:
            raise BadType("Invalid function name: " + name)
        if not isinstance(args, list):
            raise BadType("Function arguments should be specified as array")

        self._name = name
        self._args = args

    def __str__(self):
        return "{}({})".format(self._name, ", ".join(self._args))


class BaseEntity(object):
    def __repr__(self):
        return "{}[{}]".format(type(self).__name__, vars(self))

    def __str__(self):
        return self.dump(0)

    @staticmethod
    def dump_item(name, item, level):
        try:
            value = item.dump(level + 1)
            separator = "\n"
        except AttributeError:
            value = str(item)  # pass-through for native types
            separator = " "

        return "{}{}:{}{}".format(get_indent(level), name, separator, value)


class Entity(BaseEntity):
    ATTRS = None  # This should be overridden in derived classes

    def __init__(self, data):
        self.attrs = collections.OrderedDict()
        self.check_override()
        self.parse_attrs(data)

    def __getattr__(self, attr):
        try:
            return self.attrs[attr]
        except KeyError:
            raise AttributeError

    def check_override(self):
        if self.ATTRS is None:
            cls_name = self.__class__.__name__
            raise MissingImplementation(
                "{} did not override ATTRS".format(cls_name)
            )

    def parse_attrs(self, data):
        for attr, classes in self.ATTRS.items():
            if attr not in data:
                continue
            for cls in classes:
                try:
                    self.attrs[attr] = cls(data[attr])
                    break
                except BadType:
                    pass
            else:
                raise BadType("Cannot parse {}".format(data))

        wanted = set(self.ATTRS.keys())
        supplied = set(data.keys())
        missing = wanted - supplied
        extra = supplied - wanted
        return missing, extra

    def dump(self, level):
        return "\n".join(
            self.dump_item(k, v, level) for k, v in self.attrs.items()
        )


class EntityCollection(Entity):
    ITEM_CLASS = None  # This should be overridden in derived classes

    def check_override(self):
        super(EntityCollection, self).check_override()
        if self.ITEM_CLASS is None:
            cls_name = self.__class__.__name__
            raise MissingImplementation(
                "{} did not override ITEM_CLASS".format(cls_name)
            )

    def parse_attrs(self, data):
        missing, extra = super(EntityCollection, self).parse_attrs(data)
        for attr in extra:
            self.attrs[attr] = self.ITEM_CLASS(data[attr])
        return missing, set()


class OrderedEntityCollection(EntityCollection):
    ATTRS = {}  # Ordered collections cannot have any attributes

    def parse_attrs(self, data):
        for item in data:
            (attr, value), = item.items()
            self.attrs[attr] = self.ITEM_CLASS(value)
        return set(), set()


class Interface(Entity):
    ATTRS = dict(
        create=(Pass,),
    )


class InterfaceCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = Interface


class NodeTemplate(Entity):
    ATTRS = dict(
        interfaces=(InterfaceCollection,),
        type=(Pass,),
    )


class NodeTemplateCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = NodeTemplate


class TopologyTemplate(Entity):
    ATTRS = dict(
        node_templates=(NodeTemplateCollection,),
    )


class ArtifactDefinition(Entity):
    pass


class ArtifactDefinitionCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = ArtifactDefinition


class AttributeDefinition(Entity):
    ATTRS = dict(
        default=(Pass,),
        description=(Pass,),
        type=(Pass,),
    )


class AttributeDefinitionCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = AttributeDefinition


class CapabilityDefinition(Entity):
    ATTRS = dict(
        type=(String,),
    )


class CapabilityDefinitionCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = CapabilityDefinition


class OperationImplementationDefinition(Entity):
    ATTRS = dict(
        primary=(Pass,),
    )


class ParameterDefinition(Entity):
    ATTRS = dict(
        default=(Function, String),
    )


class ParameterDefinitionCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = ParameterDefinition


class OperationDefinition(Entity):
    ATTRS = dict(
        inputs=(ParameterDefinitionCollection,),
        implementation=(OperationImplementationDefinition,),
    )


class InterfaceDefinition(EntityCollection):
    ATTRS = dict(
        type=(Pass,),
    )
    ITEM_CLASS = OperationDefinition


class InterfaceDefinitionCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = InterfaceDefinition


class PropertyDefinition(Entity):
    ATTRS = dict(
        default=(Pass,),
        description=(Pass,),
        type=(Pass,),
    )


class PropertyDefinitionCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = PropertyDefinition


class RequirementDefinition(Entity):
    ATTRS = dict(
        capabilitiy=(String,),
    )


class RequirementDefinitionCollection(OrderedEntityCollection):
    ITEM_CLASS = RequirementDefinition


class NodeType(Entity):
    ATTRS = dict(
        artifacts=(ArtifactDefinitionCollection,),
        attributes=(AttributeDefinitionCollection,),
        capabilities=(CapabilityDefinitionCollection,),
        derived_from=(Pass,),
        interfaces=(InterfaceDefinitionCollection,),
        properties=(PropertyDefinitionCollection,),
        requirements=(RequirementDefinitionCollection,),
    )


class NodeTypeCollection(EntityCollection):
    ATTRS = {}
    ITEM_CLASS = NodeType

    def merge(self, other):
        duplicates = set(self.attrs.keys()) & set(other.attrs.keys())
        if len(duplicates) > 0:
            raise MergeError("Duplicated types: {}".format(duplicates))
        self.attrs.update(other.attrs)


class ServiceTemplate(Entity):
    ATTRS = dict(
        node_types=(NodeTypeCollection,),
        topology_template=(TopologyTemplate,),
        tosca_definitions_version=(String,),
    )

    def is_compatible_with(self, other):
        key = "tosca_definitions_version"
        return self.attrs[key] == other.attrs[key]

    @property
    def merge_keys(self):
        skip = (
            "tosca_definitions_version",
        )
        return (k for k in self.ATTRS if k not in skip)

    def merge(self, other):
        if not self.is_compatible_with(other):
            raise MergeError("Incompatible ServiceTemplate versions")

        for key in self.merge_keys:
            if key in other.attrs:
                if key in self.attrs:
                    self.attrs[key].merge(other.attrs[key])
                elif key in other.attrs:
                    self.attrs[key] = other.attrs[key]
