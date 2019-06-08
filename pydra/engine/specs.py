import dataclasses as dc
from hashlib import sha256
from pathlib import Path
import typing as ty

File = ty.NewType("File", Path)
Directory = ty.NewType("Directory", Path)


@dc.dataclass
class SpecInfo:
    name: str
    fields: ty.List[ty.Tuple] = dc.field(default_factory=list)
    bases: ty.Tuple[dc.dataclass] = dc.field(default_factory=tuple)


@dc.dataclass(order=True)
class BaseSpec:
    """The base dataclass specs for all inputs and outputs"""

    @property
    def hash(self):
        """Compute a basic hash for any given set of fields"""
        inp_dict = {
            field.name: getattr(self, field.name)
            for field in dc.fields(self)
            if field.name not in ["_graph"]
        }
        inp_hash = self._hash(inp_dict)
        if hasattr(self, "_graph"):

            graph_hash = [nd.checksum for nd in self._graph]
            return self._hash((inp_hash, graph_hash))
        else:
            return inp_hash

    def _hash(self, obj):
        return sha256(str(obj).encode()).hexdigest()

    def retrieve_values(self, wf, state_index=None):
        temp_values = {}
        for field in dc.fields(self):
            value = getattr(self, field.name)
            if isinstance(value, LazyField):
                value = value.get_value(wf, state_index=state_index)
                temp_values[field.name] = value
        for field, value in temp_values.items():
            setattr(self, field, value)


@dc.dataclass
class Runtime:
    rss_peak_gb: ty.Optional[float] = None
    vms_peak_gb: ty.Optional[float] = None
    cpu_peak_percent: ty.Optional[float] = None


@dc.dataclass
class Result:
    output: ty.Optional[ty.Any] = None
    runtime: ty.Optional[Runtime] = None
    errored: bool = False

    def __getstate__(self):
        state = self.__dict__.copy()
        if state["output"] is not None:
            fields = tuple(state["output"].__annotations__.items())
            state["output_spec"] = (state["output"].__class__.__name__, fields)
            state["output"] = dc.asdict(state["output"])
        return state

    def __setstate__(self, state):
        if "output_spec" in state:
            spec = list(state["output_spec"])
            del state["output_spec"]
            klass = dc.make_dataclass(spec[0], list(spec[1]))
            state["output"] = klass(**state["output"])
        self.__dict__.update(state)


@dc.dataclass
class RuntimeSpec:
    outdir: ty.Optional[str] = None
    container: ty.Optional[str] = "shell"
    network: bool = False
    """
    from CWL:
    InlineJavascriptRequirement
    SchemaDefRequirement
    DockerRequirement
    SoftwareRequirement
    InitialWorkDirRequirement
    EnvVarRequirement
    ShellCommandRequirement
    ResourceRequirement

    InlineScriptRequirement
    """


@dc.dataclass
class ShellSpec(BaseSpec):
    executable: ty.Union[str, ty.List[str]]


@dc.dataclass
class ShellOutSpec(BaseSpec):
    return_code: int
    stdout: ty.Union[File, str]
    stderr: ty.Union[File, str]


@dc.dataclass
class ContainerSpec(ShellSpec):
    image: ty.Union[File, str]
    container: ty.Union[File, str, None]
    container_xargs: ty.Optional[ty.List[str]] = None
    bindings: ty.Optional[
        ty.List[
            ty.Tuple[
                Path,  # local path
                Path,  # container path
                ty.Optional[str],  # mount mode
            ]
        ]
    ] = None


@dc.dataclass
class DockerSpec(ContainerSpec):
    container: str = "docker"


@dc.dataclass
class SingularitySpec(ContainerSpec):
    container: str = "singularity"


class LazyField:
    def __init__(self, node, attr_type):
        self.name = node.name
        if attr_type == "input":
            self.fields = [field[0] for field in node.input_spec.fields]
        elif attr_type == "output":
            self.fields = node.output_names
        else:
            raise ValueError("LazyField: Unknown attr_type: {}".format(attr_type))
        self.attr_type = attr_type
        self.field = None

    def __getattr__(self, name):
        if name in self.fields:
            self.field = name
            return self
        if name in dir(self):
            return self.__getattribute__(name)
        raise AttributeError(
            "Task {0} has no {1} attribute {2}".format(self.name, self.attr_type, name)
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        state["name"] = self.name
        state["fields"] = self.fields
        state["field"] = self.field
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __repr__(self):
        return "LF('{0}', '{1}')".format(self.name, self.field)

    def get_value(self, wf, state_index=None):
        if self.attr_type == "input":
            final_inp = getattr(wf.inputs, self.field)
            print("\n GET VAL INP", final_inp)
            return final_inp
        elif self.attr_type == "output":
            node = getattr(wf, self.name)
            # result = node.result(state_index=state_index)
            self._tmp_cnt = 0
            final_result = self._results_checking_Nones(node, state_index)
            print("BEFORE THE WHILE LOOP: final_result", final_result)
            while final_result is None:
                print("IN THE WHILE LOOP: final_result", final_result)
                final_result = self._results_checking_Nones(node, state_index)
                print("IN THE WHILE LOOP AFTER: final_result", final_result)
            print("\n GET VAL OUT", final_result)
            return final_result
            # result = self._results_checking_Nones(node, state_index)
            # if isinstance(result, list):
            #     if isinstance(result[0], list):
            #         results_new = []
            #         for res_l in result:
            #             res_l_new = [getattr(res.output, self.field) for res in res_l]
            #             results_new.append(res_l_new)
            #         return results_new
            # else:
            #     return [getattr(res.output, self.field) for res in result]
            # else:
            #     return getattr(result.output, self.field)

    def _results_checking_Nones(self, node, state_index):
        if self._tmp_cnt > 16:
            import time

            time.sleep(1)
        self._tmp_cnt += 1
        if self._tmp_cnt > 20:
            raise Exception("cant get results")
        result = node.result(state_index=state_index)

        if isinstance(result, list) and (not isinstance(result[0], list)):
            if [
                1
                for el in result
                if (el is None or getattr(el.output, self.field) is None)
            ]:
                self._results_checking_Nones(node, state_index)
            else:
                res_ret = [getattr(res.output, self.field) for res in result]
                print("\n RES RETURN 1", res_ret)
                return res_ret

        elif isinstance(result, list) and isinstance(result[0], list):
            if isinstance(result[0], list):
                tmp_none = []
                for res_l in result:
                    tmp_none += [
                        1
                        for el in res_l
                        if (el is None or getattr(el.output, self.field) is None)
                    ]
                if tmp_none:
                    self._results_checking_Nones(node, state_index)
                else:
                    results_new = []
                    for res_l in result:
                        res_l_new = [getattr(res.output, self.field) for res in res_l]
                        results_new.append(res_l_new)
                    print("\n RES RETURN 2", results_new)
                    return results_new
        else:
            if result is None or getattr(result.output, self.field) is None:
                self._results_checking_Nones(node, state_index)
            else:
                res_ret = getattr(result.output, self.field)
                print("\n RES RETURN 3", res_ret)
                return res_ret
