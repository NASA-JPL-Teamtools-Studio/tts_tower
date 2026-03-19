from tts_tower.report.components import LineBreak, HorizontalBreak

def split_with_component(component_list, splitter):
    if len(component_list) <= 1:
        return component_list
    split_list = [component_list[0]]
    for comp in component_list[1:]:
        split_list += [splitter, comp]
    return split_list

def split_with_br(component_list):
    return split_with_component(component_list, LineBreak())

def split_with_hr(component_list):
    return split_with_component(component_list, HorizontalBreak())