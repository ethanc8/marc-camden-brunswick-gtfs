//! Sanity-checks a built MARC Camden/Brunswick GTFS feed.
//!
//! `gtfs_structures::Gtfs::new` already resolves every stop_id reference in
//! stop_times.txt (an unknown stop_id is a hard error there), so just loading
//! the feed is itself a real check. This adds the checks that crate doesn't
//! do for us: every trip's route_id and service_id actually exist, and every
//! trip's stop_times are in non-decreasing time order.

use std::collections::HashSet;
use std::process::ExitCode;

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    let Some(gtfs_path) = args.next() else {
        eprintln!("usage: gtfs_validator <path-to-gtfs.zip>");
        return ExitCode::FAILURE;
    };

    let gtfs = match gtfs_structures::Gtfs::new(&gtfs_path) {
        Ok(g) => g,
        Err(e) => {
            eprintln!("failed to load {gtfs_path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    gtfs.print_stats();

    let mut problems = Vec::new();
    let known_services: HashSet<&str> = gtfs
        .calendar
        .keys()
        .map(String::as_str)
        .chain(gtfs.calendar_dates.keys().map(String::as_str))
        .collect();

    for trip in gtfs.trips.values() {
        if !gtfs.routes.contains_key(&trip.route_id) {
            problems.push(format!("trip {}: unknown route_id {}", trip.id, trip.route_id));
        }
        if !known_services.contains(trip.service_id.as_str()) {
            problems.push(format!("trip {}: unknown service_id {}", trip.id, trip.service_id));
        }

        let mut prev: Option<(u32, &str)> = None;
        for st in &trip.stop_times {
            let Some(time) = st.arrival_time.or(st.departure_time) else {
                problems.push(format!("trip {}: stop {} has no arrival or departure time", trip.id, st.stop.id));
                continue;
            };
            if let Some((prev_time, prev_stop)) = prev {
                if time < prev_time {
                    problems.push(format!(
                        "trip {}: time goes backwards from {prev_stop} ({prev_time}s) to {} ({time}s)",
                        trip.id, st.stop.id
                    ));
                }
            }
            prev = Some((time, &st.stop.id));
        }
    }

    if problems.is_empty() {
        println!("OK: no referential-integrity or ordering problems found.");
        ExitCode::SUCCESS
    } else {
        println!("{} problem(s) found:", problems.len());
        for p in &problems {
            println!("  - {p}");
        }
        ExitCode::FAILURE
    }
}
