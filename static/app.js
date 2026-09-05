let latestStatus = null;
let latestHistory = null;


async function loadStatus() {
    try {
        const response = await fetch(
            '/api/status',
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        latestStatus =
            await response.json();

        renderDashboard();

    } catch (error) {
        document.getElementById(
            'last-update'
        ).textContent =
            'Status konnte nicht geladen werden';

        console.error(
            'Status request failed:',
            error
        );
    }
}


async function loadHistory() {
    try {
        const response = await fetch(
            '/api/history',
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        latestHistory =
            await response.json();

        if (
            latestHistory.enabled
            && latestHistory.hours
        ) {
            document.getElementById(
                'history-info'
            ).textContent =
                'Historie: letzte '
                + latestHistory.hours
                + ' Stunden';
        }

        renderDashboard();

    } catch (error) {
        console.error(
            'History request failed:',
            error
        );
    }
}


function renderDashboard() {
    if (!latestStatus) {
        return;
    }

    const container =
        document.getElementById(
            'systems'
        );

    container.innerHTML = '';

    for (
        const check
        of latestStatus.checks
    ) {
        container.appendChild(
            createSystemCard(
                check
            )
        );
    }

    const lastUpdate =
        document.getElementById(
            'last-update'
        );

    if (latestStatus.generated) {
        const date = new Date(
            latestStatus.generated
        );

        lastUpdate.textContent =
            'Letzte Prüfung: '
            + date.toLocaleString();

    } else {
        lastUpdate.textContent =
            'Noch keine Prüfung durchgeführt';
    }
}


function createSystemCard(check) {
    const status = normalizeStatus(
        check.status
    );

    const card =
        document.createElement(
            'div'
        );

    card.className =
        `system ${status}`;

    const content =
        document.createElement(
            'div'
        );

    content.className =
        'system-content';


    const top =
        document.createElement(
            'div'
        );

    top.className =
        'system-top';


    const name =
        document.createElement(
            'div'
        );

    name.className =
        'name';

    name.textContent =
        check.name;


    const description =
        document.createElement(
            'div'
        );

    description.className =
        'description';

    description.textContent =
        check.description || '';


    const details =
        document.createElement(
            'div'
        );

    details.className =
        'details';

    details.textContent =
        buildDetails(
            check
        );


    const state =
        document.createElement(
            'div'
        );

    state.className =
        'state';

    state.textContent =
        status.toUpperCase();


    top.appendChild(
        name
    );

    top.appendChild(
        description
    );

    top.appendChild(
        details
    );

    top.appendChild(
        state
    );


    content.appendChild(
        top
    );

    content.appendChild(
        createTimeline(
            check.name
        )
    );

    card.appendChild(
        content
    );

    return card;
}


function buildDetails(check) {
    const details = [];

    if (
        check.http_status
        !== undefined
    ) {
        details.push(
            `HTTP ${check.http_status}`
        );
    }

    if (
        check.response_ms
        !== undefined
    ) {
        details.push(
            `${check.response_ms} ms`
        );
    }

    if (
        check.port
        !== undefined
    ) {
        details.push(
            `Port ${check.port}`
        );
    }

    if (check.error) {
        details.push(
            check.error
        );
    }

    return details.join(
        ' | '
    );
}


function createTimeline(checkName) {
    const wrapper =
        document.createElement(
            'div'
        );

    wrapper.className =
        'timeline-wrapper';


    const timeline =
        document.createElement(
            'div'
        );

    timeline.className =
        'timeline';


    if (
        !latestHistory
        || !latestHistory.enabled
        || !latestHistory.from
        || !latestHistory.to
    ) {
        const segment =
            document.createElement(
                'div'
            );

        segment.className =
            'timeline-segment unknown';

        segment.style.left =
            '0%';

        segment.style.width =
            '100%';

        timeline.appendChild(
            segment
        );

        wrapper.appendChild(
            timeline
        );

        return wrapper;
    }


    const windowStart =
        new Date(
            latestHistory.from
        ).getTime();

    const windowEnd =
        new Date(
            latestHistory.to
        ).getTime();

    const windowLength =
        windowEnd - windowStart;


    const intervals =
        (
            latestHistory.checks
            && latestHistory.checks[
                checkName
            ]
        )
        || [];


    for (
        const interval
        of intervals
    ) {
        const intervalStart =
            new Date(
                interval.from
            ).getTime();

        const intervalEnd =
            new Date(
                interval.to
            ).getTime();

        const left =
            (
                (
                    intervalStart
                    - windowStart
                )
                / windowLength
            ) * 100;

        const width =
            (
                (
                    intervalEnd
                    - intervalStart
                )
                / windowLength
            ) * 100;


        const segment =
            document.createElement(
                'div'
            );

        const status =
            normalizeStatus(
                interval.status
            );

        segment.className =
            `timeline-segment ${status}`;

        segment.style.left =
            `${Math.max(
                0,
                left
            )}%`;

        segment.style.width =
            `${Math.max(
                0,
                width
            )}%`;

        /*
         * Kurze DOWN-/UNKNOWN-Ereignisse
         * sollen trotzdem sichtbar bleiben.
         */
        if (
            status !== 'up'
            && width < 0.2
        ) {
            segment.classList.add(
                'timeline-small-event'
            );
        }

        segment.title =
            buildTimelineTooltip(
                interval
            );

        timeline.appendChild(
            segment
        );
    }


    const labels =
        document.createElement(
            'div'
        );

    labels.className =
        'timeline-labels';


    const fromLabel =
        document.createElement(
            'span'
        );

    fromLabel.textContent =
        `${latestHistory.hours}h`;


    const nowLabel =
        document.createElement(
            'span'
        );

    nowLabel.textContent =
        'jetzt';


    labels.appendChild(
        fromLabel
    );

    labels.appendChild(
        nowLabel
    );


    wrapper.appendChild(
        timeline
    );

    wrapper.appendChild(
        labels
    );


    return wrapper;
}


function buildTimelineTooltip(
    interval
) {
    const from =
        new Date(
            interval.from
        );

    const to =
        new Date(
            interval.to
        );

    return (
        interval.status.toUpperCase()
        + '\n'
        + from.toLocaleString()
        + ' - '
        + to.toLocaleString()
    );
}


function normalizeStatus(status) {
    if (
        status === 'up'
        || status === 'down'
        || status === 'unknown'
    ) {
        return status;
    }

    return 'unknown';
}


/*
 * Status häufiger aktualisieren.
 */
loadStatus();

setInterval(
    loadStatus,
    5000
);


/*
 * Historie braucht deutlich weniger
 * häufig gelesen zu werden.
 */
loadHistory();

setInterval(
    loadHistory,
    30000
);
