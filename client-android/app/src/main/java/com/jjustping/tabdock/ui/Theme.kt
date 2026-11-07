package com.jjustping.tabdock.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.graphics.vector.rememberVectorPainter
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Image
import androidx.compose.ui.graphics.ColorFilter

enum class CardStyle { FLAT, GLASS, GLOSS, WINDOW }

/** One skin = palette + card style. Same seven skins as the web UI. */
data class Skin(
    val id: String, val name: String, val desc: String,
    val bg: Brush, val card: Brush, val border: Color, val inner: Color, val innerBorder: Color,
    val text: Color, val muted: Color, val dim: Color,
    val accent: Color, val onAccent: Color, val primary: Brush,
    val green: Color, val amber: Color, val red: Color, val blue: Color,
    val radius: Dp, val style: CardStyle, val upperTitles: Boolean,
    val titleColor: Color, val tabs: Brush, val light: Boolean,
    /** Shoot cover drawn blurred under the widgets (own skins only). */
    val bgImage: String? = null,
)

private fun c(hex: Long) = Color(hex)
private fun lin(a: Color, b: Color, c3: Color? = null, d: Color? = null) = Brush.verticalGradient(listOfNotNull(a, b, c3, d))

val SKINS: List<Skin> = listOf(
    Skin("classic", "Классика", "Тёмная, как было", SolidColor(c(0xFF0A0C0F)), SolidColor(c(0xFF14171C)), c(0xFF262B34),
        c(0xFF1B1F26), c(0xFF262B34), c(0xFFE9EDF2), c(0xFF8B94A3), c(0xFF5D6573), c(0xFF4FD1C5), c(0xFF06201D),
        SolidColor(c(0xFF4FD1C5)), c(0xFF68D391), c(0xFFF6C453), c(0xFFFC8181), c(0xFF63B3ED), 18.dp, CardStyle.FLAT, true,
        c(0xFF8B94A3), SolidColor(c(0xFF0C0E12)), false),
    Skin("glass", "Liquid Glass", "Стекло и мягкий свет",
        Brush.linearGradient(listOf(c(0xFF2A2470), c(0xFF0B1020), c(0xFF0A2A5C), c(0xFF3A2410))),
        Brush.linearGradient(listOf(Color.White.copy(.16f), Color.White.copy(.05f), Color.White.copy(.08f))),
        Color.White.copy(.18f), Color.White.copy(.09f), Color.White.copy(.12f),
        c(0xFFF5F7FB), c(0xFFEBF0FF).copy(.62f), c(0xFFEBF0FF).copy(.38f), c(0xFF0A84FF), Color.White,
        lin(c(0xFF3D9BFF), c(0xFF0A7AFF)), c(0xFF30D158), c(0xFFFFD60A), c(0xFFFF453A), c(0xFF64D2FF), 28.dp, CardStyle.GLASS, false,
        c(0xFFF5F7FB), SolidColor(c(0xFF1E2234).copy(.55f)), false),
    Skin("aero-vista", "Aero · Vista", "Чёрное стекло, сияние",
        Brush.verticalGradient(listOf(Color.Black, c(0xFF02303A), c(0xFF04402A))),
        lin(c(0xFF0C1620).copy(.75f), c(0xFF081420).copy(.85f)),
        c(0xFFBEEBFF).copy(.45f), Color.White.copy(.08f), c(0xFFC8F0FF).copy(.35f),
        c(0xFFF2FBFF), c(0xFF9FC3D6), c(0xFF5F8293), c(0xFF3CD6FF), c(0xFF002838),
        lin(c(0xFFB8F5FF), c(0xFF4FD4FF), c(0xFF089AD6), c(0xFF36C6F2)), c(0xFF8EE45A), c(0xFFFFD45C), c(0xFFFF6A5C), c(0xFF59C8FF),
        10.dp, CardStyle.GLOSS, false, c(0xFFE8F8FF), lin(c(0xFF1E2A33), Color.Black), false),
    Skin("aero-seven", "Aero · Seven", "Небо, трава, пузыри",
        Brush.verticalGradient(listOf(c(0xFF2F8FE8), c(0xFF6CC0FF), c(0xFFC9ECFF), c(0xFF8EE05A))),
        lin(Color.White.copy(.92f), Color.White.copy(.6f)),
        Color.White, Color.White.copy(.65f), c(0xFF3C8CC8).copy(.45f),
        c(0xFF0C2A44), c(0xFF44708F), c(0xFF7FA3BC), c(0xFF0A8FDC), Color.White,
        lin(c(0xFF8FDCFF), c(0xFF35B4F5), c(0xFF0B8AD6), c(0xFF4CC4FF)), c(0xFF3AA61C), c(0xFFE39B00), c(0xFFE0372B), c(0xFF1A8FE0),
        16.dp, CardStyle.GLOSS, false, c(0xFF0B4F80), lin(Color.White.copy(.85f), c(0xFFC8E8FF).copy(.7f)), true),
    Skin("macosx", "Mac OS X", "Aqua и полоски", SolidColor(c(0xFFECECEC)), SolidColor(c(0xFFFBFBFB)), c(0xFF8C8C8C),
        c(0xFFF1F1F1), c(0xFF8F8F8F), c(0xFF111111), c(0xFF5D5D5D), c(0xFF9A9A9A), c(0xFF2A73D9), Color.White,
        lin(c(0xFFD4ECFF), c(0xFF74B8F4), c(0xFF2F86E8), c(0xFFB5DDFF)), c(0xFF2F9E2F), c(0xFFC88A00), c(0xFFD0342C), c(0xFF2A73D9),
        8.dp, CardStyle.WINDOW, false, c(0xFF222222), lin(c(0xFFD9D9D9), c(0xFFBDBDBD)), true),
    Skin("paper", "Бумага", "Светлый минимализм", SolidColor(c(0xFFF4F3EF)), SolidColor(Color.White), c(0xFFE4E2DB),
        c(0xFFF4F3EF), c(0xFFE4E2DB), c(0xFF17171A), c(0xFF6D6B66), c(0xFFA5A29B), c(0xFFE2552B), Color.White,
        SolidColor(c(0xFF17171A)), c(0xFF2E8B57), c(0xFFB7791F), c(0xFFC8372D), c(0xFF2F6FD6), 18.dp, CardStyle.FLAT, false,
        c(0xFF17171A), SolidColor(c(0xFFF4F3EF)), true),
    Skin("oled", "OLED", "Чёрный, монохром", SolidColor(Color.Black), SolidColor(c(0xFF0B0B0C)), c(0xFF1D1D20),
        c(0xFF141416), c(0xFF1D1D20), c(0xFFF2F2F2), c(0xFF8A8A8E), c(0xFF4C4C50), c(0xFFF2F2F2), Color.Black,
        SolidColor(c(0xFFF2F2F2)), c(0xFF8FD19E), c(0xFFE8C46A), c(0xFFFF7B72), c(0xFF9FB7FF), 16.dp, CardStyle.FLAT, false,
        c(0xFFD6D6D8), SolidColor(Color.Black), false),
)
fun skinById(id: String?) = SKINS.firstOrNull { it.id == id } ?: Themes.custom.firstOrNull { it.id == id } ?: SKINS[0]
val LocalSkin = staticCompositionLocalOf { SKINS[0] }
/** true on phones (narrow screens): one-column layouts, smaller top bar. */
val LocalCompact = androidx.compose.runtime.compositionLocalOf { false }

@Composable fun ProvideSkin(s: Skin, content: @Composable () -> Unit) = CompositionLocalProvider(LocalSkin provides s, content = content)

// ---------------- icons ----------------
private val iconCache = HashMap<String, ImageVector>()
fun iconVector(name: String): ImageVector = iconCache.getOrPut(name) {
    val paths = ICON_PATHS[name] ?: ICON_PATHS.getValue("app")
    ImageVector.Builder(name = name, defaultWidth = 24.dp, defaultHeight = 24.dp, viewportWidth = 24f, viewportHeight = 24f).apply {
        for (d in paths) addPath(pathData = PathParser().parsePathString(d).toNodes(), stroke = SolidColor(Color.White),
            strokeLineWidth = 1.8f, strokeLineCap = StrokeCap.Round, strokeLineJoin = StrokeJoin.Round, fill = null)
    }.build()
}

@Composable fun Ic(name: String, size: Dp = 22.dp, tint: Color = LocalSkin.current.text, modifier: Modifier = Modifier) {
    Image(rememberVectorPainter(iconVector(name)), null, modifier.size(size), colorFilter = ColorFilter.tint(tint))
}

// ---------------- text helpers ----------------
@Composable fun T(text: String, size: TextUnit = 15.sp, color: Color = LocalSkin.current.text, weight: FontWeight = FontWeight.Normal,
                  modifier: Modifier = Modifier, maxLines: Int = Int.MAX_VALUE, align: TextAlign? = null, mono: Boolean = false) =
    Text(text, modifier, color = color, fontSize = size, fontWeight = weight, maxLines = maxLines, overflow = TextOverflow.Ellipsis,
        textAlign = align, fontFamily = if (mono) FontFamily.Monospace else null)

// ---------------- card ----------------
@Composable
fun DeckCard(title: String?, modifier: Modifier = Modifier, action: (@Composable RowScope.() -> Unit)? = null,
             pad: Dp = 16.dp, content: @Composable ColumnScope.() -> Unit) {
    val s = LocalSkin.current
    val shape = RoundedCornerShape(s.radius)
    Column(
        modifier.clip(shape).background(s.card).border(1.dp, s.border, shape)
            .drawWithContent {
                drawContent()
                when (s.style) {
                    CardStyle.GLASS -> drawLine(Color.White.copy(.35f), Offset(size.width * .08f, 1f), Offset(size.width * .92f, 1f), 1.5f)
                    CardStyle.GLOSS -> drawRect(Brush.verticalGradient(listOf(Color.White.copy(if (s.light) .45f else .14f), Color.Transparent),
                        endY = size.height * .45f), size = size.copy(height = size.height * .45f))
                    else -> {}
                }
            }
    ) {
        if (s.style == CardStyle.WINDOW && title != null) {
            Row(Modifier.fillMaxWidth().background(lin(c(0xFFECECEC), c(0xFFD3D3D3))).padding(horizontal = 12.dp, vertical = 7.dp),
                verticalAlignment = Alignment.CenterVertically) {
                for (col in listOf(c(0xFFE0443B), c(0xFFE8B33A), c(0xFF5FBA3C))) {
                    Box(Modifier.size(12.dp).clip(CircleShape).background(col)); Spacer(Modifier.width(7.dp))
                }
                T(title, 13.sp, c(0xFF222222), FontWeight.SemiBold, Modifier.weight(1f), 1, TextAlign.Center)
                action?.invoke(this)
            }
            Column(Modifier.padding(pad), content = content)
        } else {
            Column(Modifier.padding(pad)) {
                if (title != null) {
                    Row(Modifier.fillMaxWidth().padding(bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        T(if (s.upperTitles) title.uppercase() else title, if (s.upperTitles) 13.sp else 17.sp, s.titleColor,
                            FontWeight.SemiBold, Modifier.weight(1f), 1)
                        action?.invoke(this)
                    }
                }
                content()
            }
        }
    }
}

@Composable
fun Inner(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    val s = LocalSkin.current
    val shape = RoundedCornerShape((s.radius.value * .65f).dp)
    Column(modifier.clip(shape).background(s.inner).border(1.dp, s.innerBorder.copy(alpha = .5f), shape)
        .let { if (onClick != null) it.clickable(onClick = onClick) else it }.padding(10.dp), content = content)
}

@Composable
fun Btn(text: String? = null, icon: String? = null, primary: Boolean = false, danger: Boolean = false, modifier: Modifier = Modifier,
        enabled: Boolean = true, onClick: () -> Unit) {
    val s = LocalSkin.current
    val shape = RoundedCornerShape(if (s.style == CardStyle.GLASS || s.id == "aero-seven" || s.id == "macosx") 999.dp else 14.dp)
    val fg = when { primary -> s.onAccent; danger -> s.red; else -> s.text }
    Row(modifier.height(48.dp).clip(shape)
        .background(if (primary) s.primary else SolidColor(s.inner))
        .border(1.dp, if (primary) Color.Transparent else s.innerBorder, shape)
        .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
        if (icon != null) Ic(icon, 22.dp, fg)
        if (icon != null && text != null) Spacer(Modifier.width(8.dp))
        if (text != null) T(text, 15.sp, fg, FontWeight.SemiBold, maxLines = 1)
    }
}

@Composable fun Tag(text: String, color: Color? = null) {
    val s = LocalSkin.current
    Box(Modifier.clip(RoundedCornerShape(999.dp)).background((color ?: s.muted).copy(alpha = .15f)).padding(horizontal = 8.dp, vertical = 2.dp)) {
        T(text, 12.sp, color ?: s.muted, FontWeight.SemiBold, maxLines = 1)
    }
}

@Composable fun Bar(progress: Float, color: Color? = null, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    Box(modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)).background(s.inner)) {
        Box(Modifier.fillMaxWidth(progress.coerceIn(0f, 1f)).height(8.dp).clip(RoundedCornerShape(4.dp)).background(color ?: s.accent))
    }
}

@Composable fun Spark(values: List<Double>, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    Canvas(modifier.fillMaxWidth().height(56.dp)) {
        if (values.size < 2) return@Canvas
        val step = size.width / (values.size - 1)
        val pts = values.mapIndexed { i, v -> Offset(i * step, size.height - (v.toFloat() / 100f) * (size.height - 4) - 2) }
        for (i in 1 until pts.size) drawLine(s.accent, pts[i - 1], pts[i], 2.5f, StrokeCap.Round)
    }
}

@Composable fun Empty(text: String) = T(text, 15.sp, LocalSkin.current.dim, modifier = Modifier.fillMaxWidth().padding(20.dp), align = TextAlign.Center)
@Composable fun noRipple() = remember { MutableInteractionSource() }
