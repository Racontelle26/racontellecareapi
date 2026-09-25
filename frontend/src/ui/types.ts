import type { EdgeInsets } from "react-native-safe-area-context";

import type { ThemeColors } from "../theme";
import type { useStyles } from "./styles";

export type Styles = ReturnType<typeof useStyles>;

/** Props communes à tous les écrans. */
export type ScreenProps = { styles: Styles; colors: ThemeColors; insets: EdgeInsets };
