#!/usr/bin/env bash
# Render a Claude Code statusline in the pi footer style

input=$(cat)

# Parse harness state
model=$(printf '%s' "$input" | jq -r '.model.display_name // empty' | sed 's/^Claude //')
ctx_pct=$(printf '%s' "$input" | jq -r '.context_window.used_percentage // empty')
ctx_total=$(printf '%s' "$input" | jq -r '.context_window.context_window_size // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // .workspace.current_dir // empty')
effort=$(printf '%s' "$input" | jq -r '.effort.level // empty')
rl_5h=$(printf '%s' "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
rl_7d=$(printf '%s' "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

folder=""
branch=""
if [ -n "$cwd" ]; then
    folder="${cwd##*/}"
    branch=$(git --no-optional-locks -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
fi

# Define portable Nerd Font icons
I_MODEL=$(printf '\xee\xb0\x99')   # U+EC19  nf-md-chip
I_FOLDER=$(printf '\xef\x84\x95')  # U+F115  nf-fa-folder_open
I_BRANCH=$(printf '\xef\x84\xa6')  # U+F126  nf-fa-code_fork
I_CTX=$(printf '\xef\x87\x9a')     # U+F1DA  nf-fa-history
I_BOLT=$(printf '\xef\x83\xa7')    # U+F0E7  nf-fa-bolt (thinking)
I_SEP=$(printf '\xee\x82\xb1')     # U+E0B1  powerline thin separator
I_CLOCK=$(printf '\xef\x80\x97')   # U+F017  nf-fa-clock_o

# Define the color cycle
R=$'\e[0m'
C_MODEL=$'\e[38;2;255;113;206m'   # Pink
C_THINK=$'\e[38;2;1;205;254m'     # Cyan
C_PATH=$'\e[38;2;5;255;161m'      # Mint
C_GIT=$'\e[38;2;185;103;255m'     # Purple
C_CTX=$'\e[38;2;255;251;150m'     # Yellow
C_CTX_WARN=$'\e[38;2;255;113;206m' # Pink above 70%
C_CTX_ERR=$'\e[38;2;255;60;60m'   # Red above 90%
C_RATE=$'\e[38;2;255;160;50m'      # Orange for rate limits
C_SEP=$'\e[38;2;130;80;180m'      # Purple for separators

# Format the effort label
think_label() {
    case "$1" in
        low)    echo "low"  ;;
        medium) echo "med"  ;;
        high)   echo "high" ;;
        xhigh)  echo "xhi"  ;;
        max)    echo "max"  ;;
        *)      echo "off"  ;;
    esac
}

# Build an integer percentage bar
fill_bar() {
    local pct=${1:-0} width=${2:-8}
    local filled=$(( (pct * width + 50) / 100 ))
    [ "$filled" -gt "$width" ] && filled=$width
    local bar="" i
    for ((i=0;      i<filled; i++)); do bar+="█"; done
    for ((i=filled; i<width;  i++)); do bar+="░"; done
    printf '%s' "$bar"
}

# Format compact token counts
fmt_tokens() {
    local n=$1
    if   [ "$n" -ge 1000000 ]; then printf '%sM' "$(( n / 1000000 ))"
    elif [ "$n" -ge 1000 ];    then printf '%sk' "$(( n / 1000 ))"
    else                            printf '%s'  "$n"
    fi
}

SEP=" ${C_SEP}${I_SEP}${R} "

# Build visible status segments
parts=()

# Add the model
[ -n "$model" ] && parts+=("${C_MODEL}${I_MODEL} ${model}${R}")

# Add the reported effort level
if [ -n "$effort" ]; then
    tl=$(think_label "$effort")
    parts+=("${C_THINK}${I_BOLT} think:${tl}${R}")
fi

# Add the working folder
[ -n "$folder" ] && parts+=("${C_PATH}${I_FOLDER} ${folder}${R}")

# Add the Git branch
[ -n "$branch" ] && parts+=("${C_GIT}${I_BRANCH} ${branch}${R}")

# Add context usage with warning thresholds
if [ -n "$ctx_pct" ]; then
    ctx_int=$(printf '%.0f' "$ctx_pct")
    if   [ "$ctx_int" -gt 90 ]; then cc="$C_CTX_ERR"
    elif [ "$ctx_int" -gt 70 ]; then cc="$C_CTX_WARN"
    else                             cc="$C_CTX"
    fi
    bar=$(fill_bar "$ctx_int" 8)
    ctx_str=$(printf '%.1f%%' "$ctx_pct")
    [ -n "$ctx_total" ] && ctx_str+="/$(fmt_tokens "$ctx_total")"
    parts+=("${cc}${I_CTX} ${bar} ${ctx_str}${R}")
fi

# Add available rate limits
if [ -n "$rl_5h" ]; then
    ri=$(printf '%.0f' "$rl_5h")
    parts+=("${C_RATE}${I_CLOCK} 5h:$(fill_bar "$ri" 6) ${ri}%")
fi
if [ -n "$rl_7d" ]; then
    ri=$(printf '%.0f' "$rl_7d")
    parts+=("${C_RATE}7d:$(fill_bar "$ri" 6) ${ri}%")
fi

# Join and print the segments
result=""
for part in "${parts[@]}"; do
    [ -z "$result" ] && result="$part" || result="${result}${SEP}${part}"
done
printf '%s\n' "$result"
