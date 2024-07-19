import re
import os

type_regex = r"typedef\s*(\w+)\s+(?:#\(([\(\)\w\.\s\,]+)\)\s+|)(\w+);"
# '''
# 匹配这个
# [0] = tue_fifo
# [1] = tvip_axi_item #括号内的
# [2] = tvip_axi_request_item_queue
# [3] =
# typedef tue_fifo tvip_axi_request_item_queue;
# typedef tue_fifo #(tvip_axi_item) tvip_axi_request_item_queue;

# typedef tvip_axi_sub_driver_base #(
#   .ITEM (tvip_axi_master_item )
# ) tvip_axi_master_sub_driver_base;

# typedef tvip_axi_sub_driver_base #(
#   .ITEM (tvip_axi_master_item ),
#   .ITEM (tvip_axi_master_item ),
# ) tvip_axi_master_sub_driver_base;
# '''

type_argument_pair_regex = r"\.(\w+)\s*\((\w+)\s*\)"
# '''
# 进一步细分这个
# [0] = ITEM
# [1] = tvip_axi_master_item
# .ITEM (tvip_axi_master_item ),
# '''

class_reg = r"(?:virtual\s+|)class\s+(\w+)\s+(?:#\(([\w\s\,=]+)\)\s+|)(?:extends\s+(\w+)|)(?:\s*#\(([\(\)\w\.\s\,]+)\)|)\s*;([\s\S]*?)endclass"
# '''
# 匹配 class
# [0] = tvip_axi_master_driver, class name
# [1] = class type argument
# [2] = tvip_axi_driver_base, base name
# [3] =  .ITEM         (tvip_axi_master_item         ),
#       .WRITE_DRIVER (tvip_axi_master_write_driver ),
#       .READ_DRIVER  (tvip_axi_master_read_driver  )
# [4] = class content

# virtual class tvip_axi_agent_base #(
#   type  WRITE_MONITOR = uvm_monitor,
#   type  READ_MONITOR  = uvm_monitor,
#   type  SEQUENCER     = uvm_sequencer,
#   type  DRIVER        = uvm_driver
# ) extends tue_agent #(
#   .CONFIGURATION  (tvip_axi_configuration ),
#   .STATUS         (tvip_axi_status        )
# );
# endclass
# '''

class_type_argument_regex = r"type\s+(\w+)\s+=\s+(\w+)"

function_task_regex = r"(?:(protected)\s+|)(?:(virtual)\s+|)\b(?:task|\bfunction)\s+(?:(\w+)\s+|)(\w+\([\w\s,=\"]*\));([\s\S]*?)end[functiontask]+"
# '''
# 匹配
# [0] = protected
# [1] = virtual
# [2] = return type
# [3] = function name
# [4] = arg type
# [5] = function body

# function void build_phase(uvm_phase phase);
# protected virtual task reset_if();
# '''

property_regex = r"(?:(protected)\s+|)([\w\[\]:]+)\s+([\w\[\]:$]+);"

# '''
# 匹配变量声明
# 注意：无法区分方法内的变量声明，需要去掉 function task 的搜索
# '''

constraint_regex = r"constraint\s+\w+"

classes = {}
files = []


class class_strc:
    def __init__(
        self,
        base_class="",
        class_name="",
        type_difinationes={},
        type_arguements={},
        unit=[],
    ) -> None:
        self.base_class: str = base_class
        self.class_name: str = class_name
        self.unit: list[str] = unit

        # type BASE = uvm_component -> {"BASE": "uvm_component"}
        self.type_difinationes: dict = type_difinationes

        # #(.BASE(uvm_component)) -> {"BASE": "uvm_component"}
        # #(uvm_component) -> {"default": uvm_component}
        self.type_arguements: dict = type_arguements


def extract_class_from_sv(file_name: str) -> dict:
    # step 0, read file
    with open(file_name, "r") as f:
        content = f.read()

    # step 1， search  type defined class
    result = re.findall(type_regex, content)
    for item in result:
        base_class_name, type_arguments, class_name = item
        temp_class = class_strc(base_class=base_class_name, class_name=class_name)
        if type_arguments:
            arguments = re.findall(type_argument_pair_regex, type_arguments)
            for arg in arguments:
                key, value = arg
                temp_class.type_arguements[key] = value

        classes[class_name] = temp_class

    # step 2, search class
    result = re.findall(class_reg, content)
    for item in result:
        (
            class_name,
            class_type_argument,
            base_class_name,
            base_class_type_argument,
            class_content,
        ) = item

        temp_class = class_strc(base_class=base_class_name, class_name=class_name)
        if class_type_argument:
            _type_argument = re.findall(class_type_argument_regex, class_type_argument)
            for define in _type_argument:
                key, value = define
                temp_class.type_difinationes[key] = value

        if base_class_type_argument:
            _type_argument = re.findall(
                type_argument_pair_regex, base_class_type_argument
            )
            for define in _type_argument:
                key, value = define
                temp_class.type_arguements[key] = value

        unit = extract_property_from_class(class_content)
        temp_class.unit = unit

        classes[class_name] = temp_class


def extract_property_from_class(class_content: str):
    # function
    unit = re.findall(function_task_regex, class_content)

    # constraint
    cons = re.findall(constraint_regex, class_content)
    unit += cons

    # property
    remove_func = re.sub(function_task_regex, "", class_content)
    property = re.findall(property_regex, remove_func)
    unit += property

    return unit


def convert_to_planuml():
    code = []
    connection = []
    code.append("@startuml")

    for key, value in classes.items():
        info = f"class {key}"

        if value.base_class:
            info += f" extends {value.base_class} "

        info += "{"
        code.append(info)

        if value.type_arguements:
            code.append("\tCurrent class settled arguements")
            code.append("--")
            for _k, _v in value.type_arguements.items():
                code.append(f"\t{_k}:{_v}")
                # connection.append(f"{_v}..>{key}")

        code.append("==")
        code.append("\tCurrent class type arguements")
        code.append("--")
        # class type argument
        if value.type_difinationes:
            for _k, _v in value.type_difinationes.items():
                code.append(f"\t<{_k}> {_v}")

        code.append("==")

        for item in value.unit:
            if len(item) == 5:
                # function
                if item[0] == "protected":
                    _p = "#"
                elif item[0] == "private":
                    _p = "-"
                else:
                    _p = "+"

                if item[1] == "virtual":
                    _v = "{abstract}"
                else:
                    _v = ""

                if item[2]:
                    _rt = item[2] + " "
                else:
                    _rt = ""

                arg = item[3].replace("\n", "")
                code.append(f"\t{_p}{_v}{_rt}{arg}")

            elif type(item) is str:
                # constraint
                code.append(f"\t+{item}")
            else:
                # property
                if item[0] == "protected":
                    _p = "#"
                elif item[0] == "private":
                    _p = "-"
                else:
                    _p = "+"

                code.append(f"\t{_p}{item[1]} {item[2]}")
                # if item[1] in classes:
                #     var= item[2].replace("$", "Queue")
                    # connection.append(f"{key}::{var}-->{item[1]}")
        code.append("}")

    code += connection
    code.append("@enduml")
    
    
    with open("output.puml", "w", encoding="utf-8") as f:
        f.write("\n".join(code))


def iterate_all_files(folder_path: str):
    for entry in os.scandir(folder_path):
        if entry.name.startswith("."):
            continue

        if entry.is_dir():
            iterate_all_files(entry.path)
        else:
            if "pkg" in entry.name:
                continue

            if not entry.name.endswith(".svh"):
                continue

            if entry.name == "top.sv":
                continue

            files.append(entry.path)


def main():
    iterate_all_files(r"C:\document\program\sv\tvip-axi")

    for file in files:
        extract_class_from_sv(file)

    convert_to_planuml()


if __name__ == "__main__":
    main()
