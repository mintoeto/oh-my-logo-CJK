请帮我完成项目：在终端环境中，将用户输入的字符串转为CLI中显示的ASCII字符画，且支持渐变色显示。
目前这样类似的项目只能输出提前预制好的英文，不能支持中文等语言，因此现在需要通过引入像素风格的字体文件进行采样来获得对应的字符画，具体方式如下：
- 所有像素字体文件存放在fonts文件夹下，其中包含fonts.json配置了字体的名称、路径、像素格子大小，比如：
{
    "fonts": 
    [
        {
            "name": "7px",
            "path": "DinkieBitmap-7pxDemo.ttf",
            "font_size": 8,
            "grid_size": [
                8,8
            ],
            "offset": [
                0,-1
            ]
        },
        {
            "name": "9px",
            "path": "DinkieBitmap-9pxDemo.ttf",
            "font_size": 10,
            "grid_size": [
                10,10
            ],
            "offset": [
                0,-1
            ]
        }
    ]
}
其中的grid_size说明了字体是在对应横纵行的网格中进行绘制的，比如7x7，那么采样和输出的字符画也需要基于此grid。
- 调用命令格式如下：oh-my-logo-cjk <text> [font] [palette] [options]
    - text为必选项，包含一个以双引号括起来的字符串比如："你好世界"
    - font为配置中的字体名称，如7px，无需双引号括起来；可选项，如果不输入，则默认使用配置中的第一个字体
    - palette为可选项渐变色色板，可以在终端中从左到右为字符画添加一个线性渐变，可用值如下：
    Palette 	Colors 	Description
    grad-blue 	#4ea8ff → #7f88ff 	Blue gradient (default)
    sunset 	#ff9966 → #ff5e62 → #ffa34e 	Warm sunset colors
    dawn 	#00c6ff → #0072ff 	Cool morning blues
    nebula 	#654ea3 → #eaafc8 	Purple space nebula
    ocean 	#667eea → #764ba2 	Deep ocean blues
    fire 	#ff0844 → #ffb199 	Intense fire colors
    forest 	#134e5e → #71b280 	Natural green tones
    gold 	#f7971e → #ffd200 	Luxurious gold gradient
    purple 	#667db6 → #0082c8 → #0078ff 	Royal purple to blue
    mint 	#00d2ff → #3a7bd5 	Fresh mint colors
    coral 	#ff9a9e → #fecfef 	Soft coral pink
    matrix 	#00ff41 → #008f11 	Classic matrix green
    mono 	#f07178 → #f07178 	Single coral color
    - option提供了一些可选客制化选项，如下：
    Option 	Description 	Default
    -pw, --pixel-width <pw>   每个像素输出的字符模式是全角还是半角，如果参数为h（half），则为半角的'█'和空格；如果参数为f（full），则用全角的"█"和全角空格"　"
    -d, --direction <dir> 	Gradient direction (vertical, horizontal, diagonal) 	vertical
    --letter-spacing <n> 	Letter spacing for filled mode (integer spaces between characters, 0+) 	1
    --reverse-gradient 	Reverse gradient colors 	false
    -l, --list-palettes 	Show all available color palettes 	-
    --gallery 	Render text in all available palettes 	-
    --color 	Force color output (useful for pipes) 	-
    --no-color 	Disable color output 	-
    -v, --version 	Show version number 	-
    -h, --help 	Show help information 	-

- 具体工作方式为：根据用户输入的文本，从对应字体文件字符进行对应格子的采样，按照半角或全角规则输出对应点阵字符画到CLI，需要注意字符如果达到终端最大宽度，则需要换行处理。

项目使用python实现，使用uv进行管理。