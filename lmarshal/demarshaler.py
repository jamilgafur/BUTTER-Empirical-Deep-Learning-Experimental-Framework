from typing import Iterable, Mapping, Hashable

from lmarshal.types import TypeCode


class Demarshaler:
    def __init__(self,
                 demarshaler_type_handlers: {},
                 type_field: Hashable,
                 demarshaler_object_handlers: {TypeCode: MarshallingInfo}) -> None:
        self._demarshaler_type_handlers = demarshaler_type_handlers
        self._type_field: Hashable = type_field
        self._demarshaler_object_handlers: {TypeCode: MarshallingInfo} = demarshaler_object_handlers
        self._vertex_index: [] = []
        self._vertex_visited_set = set()
        self._post_demarshal_references : [] = []

    def demarshal(self, target: any) -> any:
        # demarshal target from a plain object

        target_type = type(target)
        if target_type not in self._demarshaler_type_handlers:
            raise ValueError(f'Type has undefined demarshaling protocol: "{target_type}"')
        return self._demarshaler_type_handlers[target_type](self, target, referencing)

    def demarshal_object(self, target: any, handler) -> any:
        pass

    @staticmethod
    def demarshal_dataclass(demarshaler: 'Demarshaler', target: Mapping) -> any:
        pass

    @staticmethod
    def demarshal_list(demarshaler: 'Demarshaler', target: Iterable) -> list:
        demarshaled = []
        demarshaler._vertex_index.append(demarshaled)
        for e in target:
            demarshaled.append(demarshaler.demarshal(e, referencing))
        return demarshaled

    @staticmethod
    def demarshal_dict(demarshaler: 'Demarshaler', target: Mapping) -> any:
        type_code = target.get(demarshaler._type_field, None)
        if type_code not in demarshaler._demarshaler_object_handlers:
            raise ValueError(f'Unknown type code: "{type_code}"')
        handler = demarshaler._demarshaler_object_handlers[type_code]

        accumulator, demarshaled = handler.make_empty()
        demarshaler._vertex_index.append(demarshaled)
        for k, v in sorted(target.items()):
            # k = demarshaler.demarshal(k, False)
            accumulator[k] = demarshaler.demarshal(v, referencing)
        demarshaled = handler.demarshal(accumulator, demarshaled)
        return demarshaled

    @staticmethod
    def demarshal_string(demarshaler: 'Demarshaler', target: str) -> str:
        ref_prefix = '@'
        ref_escape = '@@'
        if target.startswith(ref_prefix):
            if target.startswith(ref_escape): # un-escape escaped strings
                target = target[len(ref_escape):]
            else:
                index = target[len(ref_prefix):]
                target = demarshaler._vertex_index[index]
        demarshaler._vertex_index.append(target)
        return target

    @staticmethod
    def demarshal_passthrough(demarshaler: 'Demarshaler', target: any) -> any:
        return target

    @staticmethod
    def demarshal_integer(demarshaler: 'Demarshaler', target: int) -> any:
        return demarshaler._vertex_index[target] if referencing else target