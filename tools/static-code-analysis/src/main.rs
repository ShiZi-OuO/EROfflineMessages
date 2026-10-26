//! PRIVATE STATIC RESEARCH ONLY. Parses bytes, never loads/executes the game.
//! dearxan's runtime disabler is NOT compiled. No process access or sockets.
use std::{env, fs, path::PathBuf, time::Instant};
use dearxan::analysis::{StubAnalyzer, analyze_all_stubs_with, encryption};
use pelite::pe64::{Pe, PeFile, PeView};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 && args.len() != 5 {return Err("usage: er-static-login-analysis exact-game.exe new-private-output-dir [hex-rva hex-size]".into());}
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().parent().unwrap().to_path_buf();
    let private = root.join("build/research/protocol-private").canonicalize()?;
    let output = PathBuf::from(&args[2]);
    if output.exists() || output.parent().ok_or("missing output parent")?.canonicalize()? != private {
        return Err("new immediate private research child directory required".into());
    }
    let bytes = fs::read(&args[1])?;
    let file = PeFile::from_bytes(&bytes).map_err(|e|format!("PE file parse: {e:?}"))?;
    let header = file.optional_header();
    if header.ImageBase != 0x140000000 || header.SizeOfImage > 256*1024*1024 {
        return Err("unsupported image base or size budget".into());
    }
    // A plain non-executable byte vector in THIS tool, not a loaded PE module.
    let mut mapped = vec![0u8; header.SizeOfImage as usize];
    let h = header.SizeOfHeaders as usize;
    mapped.get_mut(..h).ok_or("header bounds")?.copy_from_slice(bytes.get(..h).ok_or("file header bounds")?);
    for section in file.section_headers() {
        let n = section.SizeOfRawData as usize;
        let src = section.PointerToRawData as usize;
        let dst = section.VirtualAddress as usize;
        mapped.get_mut(dst..dst+n).ok_or("section destination bounds")?
            .copy_from_slice(bytes.get(src..src+n).ok_or("section file bounds")?);
    }
    let view = PeView::from_bytes(&mapped).map_err(|e|format!("PE image parse: {e:?}"))?;
    println!("Static analysis started; no game code execution/process access/network");
    let started = Instant::now();
    let infos = analyze_all_stubs_with(view, StubAnalyzer::new().max_steps(131072).trace_execution(false));
    let passed = infos.iter().filter(|v| v.is_ok()).count();
    let lists = encryption::apply_relocs_and_resolve_conflicts(
        infos.iter().filter_map(|v| v.as_ref().ok()).filter_map(|v| v.encrypted_regions.as_ref()),
        view, None)?;
    fs::create_dir(&output)?;
    // Retain only a bounded private code research window, never a decrypted game.
    let (first,size) = if args.len()==5 {
        (usize::from_str_radix(args[3].trim_start_matches("0x"),16)?,
         usize::from_str_radix(args[4].trim_start_matches("0x"),16)?)
    } else {(0xa24d00usize,0xf00usize)};
    if size==0 || size>0x4000 {return Err("private code window size budget".into());}
    let last = first.checked_add(size).ok_or("window overflow")?;
    if !file.section_headers().iter().any(|s|s.Characteristics&0x20000000!=0
        &&first>=s.VirtualAddress as usize &&last<=s.VirtualAddress as usize+s.VirtualSize as usize) {
        return Err("window must remain in an executable image section".into());
    }
    let mut window = mapped.get(first..last).ok_or("login window bounds")?.to_vec();
    let mut covered = vec![false; last-first];let mut overlaps = 0usize;
    let mut manifest = String::from("region_rva\tregion_bytes\tintersection_bytes\n");
    for list in &lists {
        for region in &list.regions {
            let a = region.rva as usize;let b = a+region.size;
            let start = first.max(a);let end = last.min(b);
            if start >= end {continue;}
            let plain = region.decrypted_slice(list).ok_or("decrypted slice bounds")?;
            window[start-first..end-first].copy_from_slice(&plain[start-a..end-a]);
            covered[start-first..end-first].fill(true);overlaps+=1;
            manifest.push_str(&format!("{:x}\t{}\t{}\n",region.rva,region.size,end-start));
        }
    }
    fs::write(output.join("login-code-window.bin"),window)?;
    fs::write(output.join("regions.tsv"),manifest)?;
    let coverage = covered.iter().filter(|v| **v).count();
    let report = format!("{{\"static_only\":true,\"process_access\":false,\"game_code_execution\":false,\"network_requests\":0,\"runtime_disabler_compiled\":false,\"stub_results\":{},\"stub_analysis_passed\":{},\"overlap_regions\":{},\"covered_window_bytes\":{},\"window_rva\":{},\"window_size\":{},\"elapsed_seconds\":{:.3}}}\n", infos.len(),passed,overlaps,coverage,first,last-first,started.elapsed().as_secs_f64());
    fs::write(output.join("report.json"),&report)?;
    println!("{report}");
    Ok(())
}
