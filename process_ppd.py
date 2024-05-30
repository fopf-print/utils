# Да, сложно
# Да, не очень красиво
# Но я горд, что не побежал переписывать это красиво на функциональном языке))
# Так что лучше так, чем не так
#
# Для простоты - читать снизу вверх

import sys
import oyaml
from collections import OrderedDict
from typing import Any, Callable


PROPERTIES_TO_PARSE = [
    'ModelName',
    'PCFileName',
]

TOKENS_TO_PICK_ONE = [
    'PageSize',
    'PageRegion',  # кажется дублирует PageSize
    'ColorModel',
    'MediaType',
    'OutputMode',
    'InputSlot',
    'Duplex',
]


Params = dict[str, list[str] | str | None]


def extract_pick_one(s: str) -> str:
    # *OpenUI *PageSize/Media Size: PickOne
    #          ^^^^^^^^

    # выбираем название БЕЗ звёздочки
    return s.split('*OpenUI *')[1].split('/')[0]


def partial(func: Callable[..., Any], *args: Any) -> Callable[..., Any]:
    def inner(*left_args: Any):
        return func(*args, *left_args)
    return inner


def parse_go_to_next_token(head: str, *tail: str) -> tuple[Params, list[str]]:
    return {}, tail


def parse_key_value_property(property_name: str, head: str, *tail: str) -> tuple[Params, list[str]]:
    # *NickName: "HP Officejet 6950, hpcups 3.23.5"
    # *ColorDevice: True
    if not head.startswith(f'*{property_name}:'):
        raise RuntimeError('wrong property name')

    property_value = head.split(': ')[1]
    if property_value[0] == '"':
        # убираем кавычки
        property_value = property_value[1:-1]
    return {property_name: property_value}, tail


def parse_pick_one(pick_one_key: str, head: str, *tail: str) -> tuple[Params, list[str]]:
    if pick_one_key not in head or not head.endswith('PickOne'):
        raise RuntimeError('wrong pick_one_key')

    values: list[str] = []
    key_with_star_and_space: str = f'*{pick_one_key} '

    while tail:
        head: str = tail[0]
        tail: list[str] = tail[1:]

        if head.startswith('*CloseUI'):
            break

        if not head.startswith(key_with_star_and_space):
            continue

        values.append(head.split(key_with_star_and_space)[1].split('/')[0])

    return {pick_one_key: values}, tail


def parse_open_ui(head: str, *tail: str) -> tuple[Params, list[str]]:
    token_x_parser: dict[str, Callable[[str, list[str]], tuple[Params, list[str]]]] = {
        token: partial(parse_pick_one, token) for token in TOKENS_TO_PICK_ONE
    }

    token = extract_pick_one(head)
    return token_x_parser.get(token, parse_go_to_next_token)(head, *tail)


def do_parse(*lines: str) -> Params:
    token_x_parser: dict[str, Callable[[str, list[str]], tuple[Params, list[str]]]] = {
        '*OpenUI': parse_open_ui,
        **{
            f'*{property_name}': partial(parse_key_value_property, property_name)
            for property_name in PROPERTIES_TO_PARSE
        }
    }

    parsed_args: Params = {}

    while lines:
        head: str = lines[0]
        start = head.split(' ')[0].replace(':', '')

        new_parsed_args, lines = token_x_parser.get(start, parse_go_to_next_token)(*lines)
        parsed_args.update(new_parsed_args)

    return parsed_args


def read_ppd_to_dict(path_to_ppd: str) -> Params:
    with open(path_to_ppd, 'r') as f:
        ppd_data = f.read()

    ppd_lines = ppd_data.split('\n')
    return do_parse(*ppd_lines)


def upsert_default_params(printer_info: Params) -> Params:
    # тут проставляем None тем параметрам, которые не нашли
    for param_name in [*PROPERTIES_TO_PARSE, *TOKENS_TO_PICK_ONE]:
        printer_info.setdefault(param_name, None)

    # если нету опций, говорим, что она ЧБ (возможно выпилить)
    printer_info.setdefault('ColorModel', 'KGray')

    return printer_info


def build_printer_configuration(parsed_ppd: Params) -> Params:
    # это надо будет подредачить ручками
    single_printer_config: Params = OrderedDict([
        ('printer-id', -1),
        ('pcfile-name', parsed_ppd['PCFileName']),
        ('printer-name', parsed_ppd['ModelName']),
        ('printer-name-display', 'красивое название принтера, чтоб показывать в тг'),
        ('printer-location', 'бла бла принтер где-то там'),
        (
            'printer-location-display',
            (
                'чуть более подробная инструкция по тому, '
                'как найти принтер (чтоб показывать пользаку по кнопочке)'
            ),
        ),
    ])

    single_printer_config['available-options'] = OrderedDict([
        # по идее не пригодится, но пусть будет
        ('PageSize', parsed_ppd['PageSize']),

        # Цветная/ЧБ печать
        ('ColorModel', parsed_ppd['ColorModel']),

        # пока оставлю, мб пригодится
        ('OutputMode', parsed_ppd['OutputMode']),

        # возможность двусторонней печати
        ('Duplex', parsed_ppd['Duplex']),

        # ('MediaType', parsed_ppd['MediaType']),  # кажется не нужно
        # ('InputSlot', parsed_ppd['InputSlot']),  # кажется не нужно
    ])

    return OrderedDict([
        ('priners', [single_printer_config]),
    ])


def main(path_to_ppd: str):
    parsed_ppd = read_ppd_to_dict(path_to_ppd)
    parsed_ppd = upsert_default_params(parsed_ppd)

    configuration = build_printer_configuration(parsed_ppd)
    print(oyaml.dump(configuration, allow_unicode=True))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(
            'Usage:\n'
            f'  python3 {sys.argv[0]} printer.ppd'
        )

    main(sys.argv[1])
