import collections

from opera import instances


def get_indent(n):
    return "  " * n


def format_path(path):
    return "/{}".format("/".join(path))


class MissingImplementation(Exception):
    pass


class UnknownAttribute(Exception):
    def __init__(self, path):
        super().__init__(format_path(path))
        self.path = path


class BadType(Exception):
    pass


class MergeError(Exception):
    pass


class Base(object):
    @classmethod
    def from_data(cls, name, data, path):
        print("Parsing {}".format(format_path(path)))
        cls.validate(data)
        return cls.parse(name, cls.normalize(data), path)

    @classmethod
    def validate(cls, data):
        pass

    @classmethod
    def normalize(cls, data):
        return data

    @classmethod
    def parse(cls, name, data, path):
        return cls(name, data, path)

    def __init__(self, name, data, path):
        self.name = name
        self.data = data
        self.path = path

    def dig(self, *path):
        if not path:
            return self
        if path[0] in self.data:
            return self.data[path[0]].dig(*path[1:])
        return None

    def dump(self, _level):
        return str(self)

    def resolve(self, _service_tempate):
        return self

    def __str__(self):
        return str(self.data)

    def __eq__(self, other):
        return self.name == other.name and self.data == other.data


class Pass(Base):
    # TODO(@tadeboro): Remove when we have enough classes implemented.
    pass


class String(Base):
    @classmethod
    def validate(cls, data):
        if not isinstance(data, str):
            raise BadType("String parser takes string as input data")

    def eval(self, _reference):
        return self.data


class Bool(Base):
    @classmethod
    def validate(cls, data):
        if not isinstance(data, bool):
            raise BadType("Bool parser takes boolean values as input")

    def eval(self, _reference):
        return self.data


class Number(Base):
    @classmethod
    def validate(cls, data):
        if not isinstance(data, (int, float)):
            raise BadType("Number parser takes numeric values as input")

    def eval(self, _reference):
        return self.data


class Reference(String):
    SECTION_PATH = None

    def resolve(self, service_template):
        if self.SECTION_PATH is None:
            raise MissingImplementation(
                "{} did not override SECTION_PATH".format(type(self).__name__)
            )

        print("Resolving {} in {}".format(self.data, self.SECTION_PATH))
        target = service_template.dig(*self.SECTION_PATH, self.data)
        if target is None:
            raise Exception("Invalid reference /{}".format(
                "/".join(self.SECTION_PATH + (self.data,)),
            ))
        return target


class NodeTypeReference(Reference):
    SECTION_PATH = ("node_types",)


class NodeTemplateReference(Reference):
    SECTION_PATH = ("topology_template", "node_templates")


class Function(Base):
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

    @classmethod
    def validate(cls, data):
        if not isinstance(data, dict):
            raise BadType("Function constructor takes dict as input data")
        if len(data) != 1:
            raise BadType("Function constructor takes single member dict")
        (name, args), = data.items()
        if name not in cls.VALID_NAMES:
            raise BadType("Invalid function name: " + name)
        if not isinstance(args, list):
            raise BadType("Function arguments should be specified as array")
        if len(args) < 1:
            raise BadType("Function takes at least one argument")

    @classmethod
    def parse(cls, name, data, path):
        (function, arguments), = data.items()
        return super().parse(name, dict(
            function=String.from_data(function, function, path + [function]),
            arguments=[
                Value.from_data(str(i), a, path + [function, str(i)])
                for i, a in enumerate(arguments)
            ]
        ), path)

    def __str__(self):
        return "{}({})".format(
            self.data["function"],
            ", ".join(map(str, self.data["arguments"])),
        )

    def resolve(self, service_template):
        # TODO(@tadeboro): resolve arguments here
        return self

    def eval(self, reference):
        function = str(self.data["function"])
        arguments = [a.eval(reference) for a in self.data["arguments"]]
        return getattr(reference, function)(*arguments)


class Value(Base):
    CLASS_PRIORITY = (Function, Number, Bool, String, Pass)

    @classmethod
    def validate(cls, data):
        pass  # TODO(@tadeboro): write down validator

    @classmethod
    def parse(cls, name, data, path):
        for klass in cls.CLASS_PRIORITY:
            try:
                return klass.from_data(name, data, path)
            except BadType as e:
                print(e)
                pass
        raise Exception("Should not be here: Pass should always parse")


class Entity(Base):
    ATTRS = {}  # This can be overridden in derived classes
    ITEM_CLASS = None  # This can be overridden in derived classes

    @classmethod
    def validate(cls, data):
        if not isinstance(data, dict):
            raise BadType("{} can only be constructed from dict".format(
                cls.__name__,
            ))

    @classmethod
    def parse(cls, name, data, path):
        children = {k: cls.parse_attr(k, v, path) for k, v in data.items()}
        return super().parse(name, children, path)

    @classmethod
    def parse_attr(cls, name, data, path):
        klass = cls.ATTRS.get(name, cls.ITEM_CLASS)
        if klass is None:
            raise UnknownAttribute(path)
        return klass.from_data(name, data, path + [name])

    def __str__(self):
        return self.dump(0)

    def __getattr__(self, key):
        try:
            return self.data[key]
        except KeyError:
            raise AttributeError(key)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def dump(self, level):
        indent = get_indent(level)
        children = []
        for k, v in self.data.items():
            child = v.dump(level + 1)
            separator = "\n" if "\n" in child or ":" in child else " "
            children.append("{}{}:{}{}".format(indent, k, separator, child))
        return "\n".join(children)

    def resolve(self, service_template):
        for k, v in self.data.items():
            self.data[k] = v.resolve(service_template)
        return self


class OrderedEntity(Entity):
    @classmethod
    def validate(cls, data):
        if not isinstance(data, list):
            raise BadType("Ordered collections should be created from lists")

    @classmethod
    def normalize(cls, data):
        # Convert list of single-entry dicts into ordered dict
        result = collections.OrderedDict()
        for item in data:
            (k, v), = item.items()
            result[k] = v
        return result


class PropertyDefinition(Entity):
    ATTRS = dict(
        description=String,
        required=Bool,
        default=Value,

        type=Pass,
    )


class PropertyDefinitionCollection(Entity):
    ITEM_CLASS = PropertyDefinition


class Requirement(Entity):
    pass


class RequirementCollection(OrderedEntity):
    ITEM_CLASS = NodeTemplateReference


class PropertyAssignmentCollection(Entity):
    ITEM_CLASS = Value


class ArtifactDefinition(Entity):
    pass


class ArtifactDefinitionCollection(Entity):
    ITEM_CLASS = ArtifactDefinition


class AttributeDefinition(Entity):
    ATTRS = dict(
        description=String,

        default=Pass,
        type=String,
        entry_schema=Pass,
    )


class AttributeDefinitionCollection(Entity):
    ITEM_CLASS = AttributeDefinition


class CapabilityDefinition(Entity):
    ATTRS = dict(
        type=String,
        valid_source_types=Pass,
    )


class CapabilityDefinitionCollection(Entity):
    ITEM_CLASS = CapabilityDefinition


class OperationImplementationDefinition(Entity):
    ATTRS = dict(
        primary=String,
    )

    @classmethod
    def validate(cls, data):
        if not isinstance(data, (str, dict)):
            raise BadType("OperationImplementationDefinition cannot parse")

    @classmethod
    def normalize(cls, data):
        if isinstance(data, str):
            return {"primary": data}
        return data


class ParameterDefinition(Entity):
    ATTRS = dict(
        default=Value,
    )


class ParameterDefinitionCollection(Entity):
    ITEM_CLASS = ParameterDefinition


class OperationDefinition(Entity):
    ATTRS = dict(
        inputs=ParameterDefinitionCollection,
        implementation=OperationImplementationDefinition,
    )

    @classmethod
    def validate(cls, data):
        if not isinstance(data, (str, dict)):
            raise BadType("OperationDefinition cannot parse")

    @classmethod
    def normalize(cls, data):
        if isinstance(data, str):
            return {"implementation": {"primary": data}}
        return data


class Operation(Entity):
    ATTRS = dict(
        inputs=PropertyAssignmentCollection,
        implementation=OperationImplementationDefinition,
    )

    @classmethod
    def validate(cls, data):
        if not isinstance(data, (str, dict)):
            raise BadType("Operation cannot parse")

    @classmethod
    def normalize(cls, data):
        if isinstance(data, str):
            return {"implementation": {"primary": data}}
        return data


class Interface(Entity):
    ATTRS = dict(
        inputs=PropertyAssignmentCollection,
    )
    ITEM_CLASS = Operation


class InterfaceCollection(Entity):
    ITEM_CLASS = Interface


class InterfaceDefinition(Entity):
    ATTRS = dict(
        type=Pass,
        inputs=PropertyDefinitionCollection,
    )
    ITEM_CLASS = OperationDefinition


class InterfaceDefinitionCollection(Entity):
    ITEM_CLASS = InterfaceDefinition


class NodeTemplate(Entity):
    ATTRS = dict(
        interfaces=InterfaceCollection,
        properties=PropertyAssignmentCollection,
        requirements=RequirementCollection,
        type=NodeTypeReference,
    )

    def instantiate(self, name):
        self.instances = [instances.Instance(name, self)]
        return self.instances

    def get_operation_inputs(self, interface, name):
        interface = self.dig("interfaces", interface)
        if interface is None:
            return {}

        inputs = (interface.dig("inputs", "data") or {}).copy()
        inputs.update(interface.dig(name, "inputs", "data") or {})
        return {i.name: i for i in inputs.values()}

    def get_operation(self, interface, name):
        implementation, inputs = self.type.get_operation(interface, name)
        inputs.update(self.get_operation_inputs(interface, name))
        op_impl = self.dig("interfaces", interface, name, "implementation")
        return op_impl or implementation, inputs

    def get_requirement_property(self, name, *path):
        if name in self.requirements.data:
            return self.requirements.data[name].get_property("SELF", *path)
        return None

    def get_property(self, reference, name, *path):
        if reference not in ("SELF", "SOURCE", "TARGET"):
            raise Exception(
                "Accessing non-local stuff bad. Fix your service template."
            )

        # TODO(@tadeboro): Generalize property access when we have support for
        # data types and property dicts.
        prop = (
            self.dig("properties", name) or
            self.type.get_property(name, *path) or
            self.dig("capabilities", "properties", name)
        )
        if prop:
            return prop.eval(self)
        else:
            return self.get_requirement_property(name, *path)


class NodeTemplateCollection(Entity):
    ITEM_CLASS = NodeTemplate


class TopologyTemplate(Entity):
    ATTRS = dict(
        node_templates=NodeTemplateCollection,
    )


class RequirementDefinition(Entity):
    ATTRS = dict(
        capability=String,

        node=Pass,
        relationship=Pass,
        occurrences=Pass,
    )


class RequirementDefinitionCollection(OrderedEntity):
    ITEM_CLASS = RequirementDefinition


class NodeType(Entity):
    ATTRS = dict(
        artifacts=ArtifactDefinitionCollection,
        attributes=AttributeDefinitionCollection,
        capabilities=CapabilityDefinitionCollection,
        derived_from=NodeTypeReference,
        interfaces=InterfaceDefinitionCollection,
        properties=PropertyDefinitionCollection,
        requirements=RequirementDefinitionCollection,

        description=Pass,
    )

    def get_operation_inputs(self, interface, name):
        interface = self.dig("interfaces", interface)
        if interface is None:
            return {}

        inputs = {}
        if interface.dig("inputs"):
            inputs.update(interface.inputs.data)
        if interface.dig(name, "inputs"):
            inputs.update(interface[name].inputs.data)
        return {
            i.name: i.default for i in inputs.values() if i.dig("default")
        }

    def get_operation(self, interface, name):
        parent = self.dig("derived_from")
        if parent:
            implementation, inputs = parent.get_operation(interface, name)
        else:
            implementation, inputs = None, {}

        op_impl = self.dig("interfaces", interface, name, "implementation")
        inputs.update(self.get_operation_inputs(interface, name))
        return op_impl or implementation, inputs


class NodeTypeCollection(Entity):
    ITEM_CLASS = NodeType

    def merge(self, other):
        duplicates = set(self.data.keys()) & set(other.data.keys())
        if len(duplicates) > 0:
            raise MergeError("Duplicated types: {}".format(duplicates))
        self.data.update(other.data)


class RelationshipType(Entity):
    ATTRS = dict(
        derived_from=String,
        valid_target_types=Pass,
        interfaces=Pass,
    )


class RelationshipTypeCollection(Entity):
    ITEM_CLASS = RelationshipType


class ServiceTemplate(Entity):
    ATTRS = dict(
        node_types=NodeTypeCollection,
        relationship_types=RelationshipTypeCollection,
        topology_template=TopologyTemplate,
        tosca_definitions_version=String,
    )
    MERGE_FIELDS = (
        "node_types",
        "topology_template",
    )

    @classmethod
    def from_data(cls, data):
        return super().from_data("ROOT", data, [])

    def is_compatible_with(self, oth):
        return self.tosca_definitions_version == oth.tosca_definitions_version

    def merge(self, other):
        if not self.is_compatible_with(other):
            raise MergeError("Incompatible ServiceTemplate versions")

        for key in self.MERGE_FIELDS:
            if key in self.data:
                self.data[key].merge(other.data[key])
            else:
                self.data[key] = other.data[key]

    def resolve(self):
        return super().resolve(self)

    def instantiate(self):
        instance_model = instances.InstanceModel(self)
        for name, item in self.topology_template.node_templates.data.items():
            instance_model.add(item.instantiate(name))
        instance_model.link()
        # TODO(@tadeboro): validate graph
        return instance_model
